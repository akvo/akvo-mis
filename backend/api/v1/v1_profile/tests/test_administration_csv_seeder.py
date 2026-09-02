import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.bbox import get_bbox_attribute, resolve_bbox
from api.v1.v1_profile.constants import BBOX_ATTRIBUTE_NAME
from api.v1.v1_profile.management.commands.administration_csv_seeder import (
    build_row_data,
    parse_attribute_headers,
    parse_headers,
    resolve_source,
)
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    AdministrationAttributeValue,
    Levels,
)
from api.v1.v1_users.models import Tenant

THREE_TIER = (
    "0_National,0_Code,1_Province,1_Code,2_District,2_Code\n"
    "Indonesia,ID,Central Java,CJ,Semarang,CJ-SMG\n"
    "Indonesia,ID,Central Java,CJ,Solo,CJ-SLO\n"
    "Indonesia,ID,Yogyakarta,YK,Sleman,YK-SLM\n"
)


class CsvSeederMixin:
    """Temp CSVs and workspaces, cleaned up per test."""

    def write_csv(self, content, name="admin.csv"):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def make_tenant(self, subdomain):
        """A registered-but-unconfigured workspace: no levels, no root."""
        return Tenant.objects.create(subdomain=subdomain)

    def configure(self, tenant, level_0_name, root_name):
        """What configure_project() leaves behind: level 0 plus a root."""
        level = Levels.objects.create(
            name=level_0_name, level=0, tenant=tenant
        )
        root = Administration.objects.create(
            parent=None, level=level, name=root_name, tenant=tenant
        )
        return level, root

    def seed(self, content, tenant, **kwargs):
        call_command(
            "administration_csv_seeder",
            "--source", self.write_csv(content),
            "--tenant", tenant.subdomain,
            **kwargs,
        )


class ParseHeadersTest(TestCase):
    """The header grammar is the whole contract with the file author."""

    def test_parses_level_prefixed_headers(self):
        parsed = parse_headers(
            ["0_National", "0_Code", "1_Province", "1_Code"]
        )
        self.assertEqual(parsed[0], ("0_National", "National", "0_Code"))
        self.assertEqual(parsed[1], ("1_Province", "Province", "1_Code"))

    def test_code_columns_are_optional(self):
        parsed = parse_headers(["0_National", "1_Province"])
        self.assertIsNone(parsed[0][2])
        self.assertIsNone(parsed[1][2])

    def test_alias_may_contain_underscores_and_digits(self):
        # The suffix form (`Region_2_1`) misparses exactly this.
        parsed = parse_headers(["0_Sub_Region_2"])
        self.assertEqual(parsed[0], ("0_Sub_Region_2", "Sub_Region_2", None))

    def test_ignores_non_level_columns(self):
        parsed = parse_headers(
            ["0_National", "Population", "notes", "1_Province"]
        )
        self.assertEqual(sorted(parsed), [0, 1])

    def test_rejects_non_contiguous_levels(self):
        with self.assertRaisesMessage(CommandError, "contiguous from 0"):
            parse_headers(["0_National", "1_Province", "3_Village"])

    def test_rejects_file_with_no_level_columns(self):
        with self.assertRaisesMessage(CommandError, "No level columns"):
            parse_headers(["Name", "Code"])

    def test_rejects_two_name_columns_for_one_level(self):
        with self.assertRaisesMessage(CommandError, "Two name columns"):
            parse_headers(["0_National", "1_Province", "1_Region"])

    def test_level_named_code_is_reported_as_a_missing_tier(self):
        # `1_Code` is claimed as level 1's CODE column, so level 1 has no
        # name column and the tier goes missing. Rejected either way, but
        # the message a file author sees is the contiguity one.
        with self.assertRaisesMessage(CommandError, "contiguous from 0"):
            parse_headers(["0_National", "1_Code", "2_District"])


class ResolveSourceTest(TestCase):
    """Storage is the intended home; a literal path is the fallback."""

    def setUp(self):
        self.storage = tempfile.mkdtemp()

    def test_prefers_storage_over_an_identically_named_local_file(self):
        os.makedirs(os.path.join(self.storage, "administrations"))
        in_storage = os.path.join(
            self.storage, "administrations", "x.csv"
        )
        with open(in_storage, "w") as handle:
            handle.write("0_National\nFiji\n")
        with override_settings(STORAGE_PATH=self.storage):
            resolved = resolve_source("administrations/x.csv")
        self.assertEqual(resolved, in_storage)

    def test_falls_back_to_a_literal_path(self):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "scratch.csv")
        with open(path, "w") as handle:
            handle.write("0_National\nFiji\n")
        with override_settings(STORAGE_PATH=self.storage):
            self.assertEqual(resolve_source(path), path)

    def test_error_names_both_locations(self):
        with override_settings(STORAGE_PATH=self.storage):
            with self.assertRaises(CommandError) as caught:
                resolve_source("nope.csv")
        message = str(caught.exception)
        self.assertIn(self.storage, message)
        self.assertIn("file path", message)


class TenantArgumentTest(CsvSeederMixin, TestCase):
    """--tenant is required, and is checked before the file is opened."""

    def test_tenant_is_required(self):
        with self.assertRaises(CommandError):
            call_command(
                "administration_csv_seeder",
                "--source", self.write_csv(THREE_TIER),
            )

    def test_unknown_subdomain_is_rejected(self):
        self.make_tenant("acme")
        with self.assertRaisesMessage(CommandError, "No workspace with"):
            call_command(
                "administration_csv_seeder",
                "--source", self.write_csv(THREE_TIER),
                "--tenant", "ghost",
            )

    def test_unknown_subdomain_lists_known_ones(self):
        self.make_tenant("acme")
        with self.assertRaises(CommandError) as caught:
            call_command(
                "administration_csv_seeder",
                "--source", self.write_csv(THREE_TIER),
                "--tenant", "ghost",
            )
        self.assertIn("acme", str(caught.exception))


class ImportTest(CsvSeederMixin, TestCase):
    """The happy path, on a workspace that has never been configured."""

    def setUp(self):
        self.tenant = self.make_tenant("acme")

    def test_creates_levels_and_units(self):
        self.seed(THREE_TIER, self.tenant)

        levels = Levels.objects.filter(tenant=self.tenant).order_by("level")
        self.assertEqual(
            [(level.level, level.name) for level in levels],
            [(0, "National"), (1, "Province"), (2, "District")],
        )
        # 1 root + 2 provinces + 3 districts
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 6
        )

    def test_repeated_parent_tiers_are_reused_not_duplicated(self):
        self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(
                tenant=self.tenant, name__iexact="Central Java"
            ).count(),
            1,
        )

    def test_codes_are_stored(self):
        self.seed(THREE_TIER, self.tenant)
        semarang = Administration.objects.get(
            tenant=self.tenant, name__iexact="Semarang"
        )
        self.assertEqual(semarang.code, "CJ-SMG")

    def test_path_is_populated_and_full_name_renders_ancestry(self):
        # `path` is what every visualization administration filter reads.
        self.seed(THREE_TIER, self.tenant)
        semarang = Administration.objects.get(
            tenant=self.tenant, name__iexact="Semarang"
        )
        root = Administration.objects.get(
            tenant=self.tenant, parent__isnull=True
        )
        province = semarang.parent
        self.assertEqual(
            semarang.path, f"{root.id}.{province.id}."
        )
        self.assertEqual(
            semarang.full_name, "Indonesia - Central Java - Semarang"
        )

    def test_import_is_idempotent(self):
        self.seed(THREE_TIER, self.tenant)
        before = Administration.objects.filter(tenant=self.tenant).count()
        self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(),
            before,
        )

    def test_blank_tail_truncates_the_path(self):
        content = (
            "0_National,1_Province,2_District\n"
            "Indonesia,Central Java,Semarang\n"
            "Indonesia,Yogyakarta,\n"
        )
        self.seed(content, self.tenant)
        yogya = Administration.objects.get(
            tenant=self.tenant, name__iexact="Yogyakarta"
        )
        self.assertEqual(yogya.parent_administration.count(), 0)

    def test_names_are_title_cased_matching_the_excel_path(self):
        # Accepted behaviour (R-1): seed_administrations applies .title().
        # Asserted so a later change to the shared helper is caught here.
        content = "0_National,1_Province\nIndonesia,DKI Jakarta\n"
        self.seed(content, self.tenant)
        self.assertTrue(
            Administration.objects.filter(
                tenant=self.tenant, name="Dki Jakarta"
            ).exists()
        )

    def test_attribute_columns_are_ignored_without_error(self):
        content = (
            "0_National,1_Province,Population\n"
            "Indonesia,Central Java,36000000\n"
        )
        self.seed(content, self.tenant)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 2
        )


class SameNameDifferentParentTest(CsvSeederMixin, TestCase):
    """The defect administration_seeder has and this command must not."""

    def test_same_name_under_different_parents_stays_distinct(self):
        tenant = self.make_tenant("acme")
        content = (
            "0_National,1_Province,2_District\n"
            "Fiji,Central,Nasau\n"
            "Fiji,Western,Nasau\n"
        )
        self.seed(content, tenant)

        nasau = list(
            Administration.objects.filter(
                tenant=tenant, name__iexact="Nasau"
            ).order_by("id")
        )
        self.assertEqual(len(nasau), 2)
        self.assertNotEqual(nasau[0].parent_id, nasau[1].parent_id)
        # And the paths must differ, or every visualization administration
        # filter silently merges them.
        self.assertNotEqual(nasau[0].path, nasau[1].path)


class RootReconciliationTest(CsvSeederMixin, TestCase):
    """A tenant has exactly one root; the file must agree with it."""

    def setUp(self):
        self.tenant = self.make_tenant("acme")

    def test_matching_root_is_reused(self):
        _level, root = self.configure(self.tenant, "National", "Indonesia")
        self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(
                tenant=self.tenant, parent__isnull=True
            ).count(),
            1,
        )
        root.refresh_from_db()
        self.assertEqual(root.name, "Indonesia")

    def test_root_match_is_case_insensitive(self):
        self.configure(self.tenant, "National", "INDONESIA")
        self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(
                tenant=self.tenant, parent__isnull=True
            ).count(),
            1,
        )

    def test_mismatched_root_is_rejected_and_writes_nothing(self):
        self.configure(self.tenant, "National", "Acme Water")
        with self.assertRaisesMessage(CommandError, "--rename-root"):
            self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 1
        )

    def test_rename_root_renames_instead(self):
        _level, root = self.configure(self.tenant, "National", "Acme Water")
        self.seed(THREE_TIER, self.tenant, rename_root=True)
        root.refresh_from_db()
        self.assertEqual(root.name, "Indonesia")
        self.assertEqual(
            Administration.objects.filter(
                tenant=self.tenant, parent__isnull=True
            ).count(),
            1,
        )

    def test_more_than_one_root_value_is_rejected(self):
        content = (
            "0_National,1_Province\n"
            "Indonesia,Central Java\n"
            "Malaysia,Johor\n"
        )
        with self.assertRaisesMessage(CommandError, "more than one value"):
            self.seed(content, self.tenant)

    def test_blank_level_zero_with_a_descendant_is_a_skipped_tier(self):
        content = "0_National,1_Province\n,Central Java\n"
        with self.assertRaisesMessage(CommandError, "cannot skip"):
            self.seed(content, self.tenant)

    def test_entirely_blank_row_is_rejected(self):
        content = "0_National,1_Province\nIndonesia,Central Java\n,\n"
        with self.assertRaisesMessage(CommandError, "level 0 may not"):
            self.seed(content, self.tenant)


class ExistingLevelsTest(CsvSeederMixin, TestCase):
    """A workspace that already named its tiers keeps those names."""

    def test_existing_level_keeps_its_name(self):
        tenant = self.make_tenant("acme")
        self.configure(tenant, "National", "Indonesia")
        Levels.objects.create(name="Province", level=1, tenant=tenant)

        content = "0_National,1_Provinsi\nIndonesia,Central Java\n"
        self.seed(content, tenant)

        level_one = Levels.objects.get(tenant=tenant, level=1)
        self.assertEqual(level_one.name, "Province")


class SkippedTierTest(CsvSeederMixin, TestCase):
    """A hole in the middle of a path is a broken file, not a truncation."""

    def test_blank_middle_tier_is_rejected(self):
        tenant = self.make_tenant("acme")
        content = (
            "0_National,1_Province,2_District\n"
            "Indonesia,,Semarang\n"
        )
        with self.assertRaisesMessage(CommandError, "cannot skip"):
            self.seed(content, tenant)

    def test_error_names_the_row_and_column(self):
        tenant = self.make_tenant("acme")
        content = (
            "0_National,1_Province,2_District\n"
            "Indonesia,Central Java,Semarang\n"
            "Indonesia,,Solo\n"
        )
        with self.assertRaises(CommandError) as caught:
            self.seed(content, tenant)
        message = str(caught.exception)
        self.assertIn("Row 3", message)
        self.assertIn("1_Province", message)


class DryRunTest(CsvSeederMixin, TestCase):
    def test_dry_run_writes_nothing(self):
        tenant = self.make_tenant("acme")
        self.seed(THREE_TIER, tenant, dry_run=True)
        self.assertEqual(
            Administration.objects.filter(tenant=tenant).count(), 0
        )
        self.assertEqual(Levels.objects.filter(tenant=tenant).count(), 0)


class TenantIsolationTest(CsvSeederMixin, TestCase):
    """The same file imported twice yields two independent hierarchies."""

    def test_two_tenants_get_independent_hierarchies(self):
        acme = self.make_tenant("acme")
        beta = self.make_tenant("beta")
        self.seed(THREE_TIER, acme)
        self.seed(THREE_TIER, beta)

        for tenant in (acme, beta):
            self.assertEqual(
                Administration.objects.filter(tenant=tenant).count(), 6
            )
            self.assertEqual(
                Levels.objects.filter(tenant=tenant).count(), 3
            )
        acme_names = set(
            Administration.objects.filter(tenant=acme).values_list(
                "id", flat=True
            )
        )
        beta_names = set(
            Administration.objects.filter(tenant=beta).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(acme_names & beta_names, set())


class BuildRowDataTest(CsvSeederMixin, TestCase):
    def test_orders_root_first_and_stops_at_the_first_blank(self):
        tenant = self.make_tenant("acme")
        header_map = {
            0: ("0_National", "National", None),
            1: ("1_Province", "Province", "1_Code"),
            2: ("2_District", "District", None),
        }
        levels = {
            depth: Levels.objects.create(
                name=str(depth), level=depth, tenant=tenant
            )
            for depth in range(3)
        }
        row = {
            "0_National": "Indonesia",
            "1_Province": "Central Java",
            "1_Code": "CJ",
            "2_District": "",
        }
        data = build_row_data(header_map, row, levels)
        self.assertEqual(
            [(item[1], item[2]) for item in data],
            [("Indonesia", None), ("Central Java", "CJ")],
        )


THREE_TIER_WITH_BBOX = (
    "0_National,0_Code,1_Province,1_Code,2_District,2_Code,"
    "attr_Bounding Box\n"
    "Indonesia,ID,Central Java,CJ,Semarang,CJ-SMG,"
    '"110.2,-7.1,110.5,-6.9"\n'
    "Indonesia,ID,Central Java,CJ,Solo,CJ-SLO,"
    '"110.7,-7.7,110.9,-7.5"\n'
    "Indonesia,ID,Yogyakarta,YK,Sleman,YK-SLM,"
    '"110.3,-7.8,110.5,-7.6"\n'
)


class ParseAttributeHeadersTest(TestCase):
    """`attr_` columns are the hook SEED-002 left for exactly this."""

    def test_recognises_an_attribute_column(self):
        self.assertEqual(
            parse_attribute_headers(["0_National", "attr_Bounding Box"]),
            {"attr_Bounding Box": "Bounding Box"},
        )

    def test_ignores_files_without_any(self):
        self.assertEqual(parse_attribute_headers(["0_National"]), {})

    def test_rejects_an_empty_name(self):
        with self.assertRaisesMessage(CommandError, "no attribute name"):
            parse_attribute_headers(["attr_"])

    def test_rejects_two_columns_for_one_attribute(self):
        with self.assertRaisesMessage(CommandError, "Two columns"):
            parse_attribute_headers(["attr_Population", "attr_Population "])

    def test_level_columns_are_not_attributes(self):
        self.assertEqual(parse_attribute_headers(["0_National", "0_Code"]),
                         {})


@override_settings(TEST_ENV=True)
class AttributeImportTest(CsvSeederMixin, TestCase):
    def setUp(self):
        self.tenant = self.make_tenant("acme")
        self.configure(self.tenant, "National", "Indonesia")

    def leaf(self, name):
        return Administration.objects.get(name=name, tenant=self.tenant)

    def test_creates_the_attribute_once(self):
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        self.assertEqual(
            AdministrationAttribute.objects.filter(
                name=BBOX_ATTRIBUTE_NAME, tenant=self.tenant
            ).count(),
            1,
        )

    def test_stores_a_value_on_the_deepest_unit_only(self):
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        attribute = get_bbox_attribute(self.tenant)
        with_value = AdministrationAttributeValue.objects.filter(
            attribute=attribute
        )
        # Three leaves, and nothing on the provinces or the root.
        self.assertEqual(with_value.count(), 3)
        self.assertEqual(
            set(with_value.values_list("administration__name", flat=True)),
            {"Semarang", "Solo", "Sleman"},
        )

    def test_the_stored_box_round_trips(self):
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        attribute = get_bbox_attribute(self.tenant)
        self.assertEqual(
            resolve_bbox(self.leaf("Semarang"), attribute),
            (110.2, -7.1, 110.5, -6.9),
        )

    def test_reimport_upserts_rather_than_duplicating(self):
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        self.assertEqual(
            AdministrationAttributeValue.objects.count(), 3
        )
        self.assertEqual(
            AdministrationAttribute.objects.filter(
                name=BBOX_ATTRIBUTE_NAME
            ).count(),
            1,
        )

    def test_a_file_without_attributes_still_imports(self):
        # Every CSV written before SEED-003.
        self.seed(THREE_TIER, self.tenant)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 6
        )
        self.assertEqual(AdministrationAttributeValue.objects.count(), 0)

    def test_a_malformed_box_names_the_row_and_rolls_back(self):
        broken = THREE_TIER_WITH_BBOX.replace(
            '"110.7,-7.7,110.9,-7.5"', '"110.7,-7.7"'
        )
        with self.assertRaisesMessage(CommandError, "Row 3"):
            self.seed(broken, self.tenant)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 1
        )

    def test_an_inverted_box_is_rejected(self):
        broken = THREE_TIER_WITH_BBOX.replace(
            '"110.2,-7.1,110.5,-6.9"', '"110.5,-6.9,110.2,-7.1"'
        )
        with self.assertRaisesMessage(CommandError, "min < max"):
            self.seed(broken, self.tenant)

    def test_a_blank_cell_writes_nothing(self):
        partial = THREE_TIER_WITH_BBOX.replace(
            '"110.7,-7.7,110.9,-7.5"', ""
        )
        self.seed(partial, self.tenant)
        self.assertEqual(AdministrationAttributeValue.objects.count(), 2)

    def test_dry_run_writes_no_attributes(self):
        self.seed(THREE_TIER_WITH_BBOX, self.tenant, dry_run=True)
        self.assertEqual(AdministrationAttribute.objects.count(), 0)
        self.assertEqual(AdministrationAttributeValue.objects.count(), 0)

    def test_two_workspaces_get_separate_attributes(self):
        # Attribute names are not globally unique; an unscoped lookup would
        # hand one workspace the other's definition.
        beta = self.make_tenant("beta")
        self.configure(beta, "National", "Indonesia")
        self.seed(THREE_TIER_WITH_BBOX, self.tenant)
        self.seed(THREE_TIER_WITH_BBOX, beta)
        self.assertEqual(
            AdministrationAttribute.objects.filter(
                name=BBOX_ATTRIBUTE_NAME
            ).count(),
            2,
        )
        self.assertNotEqual(
            get_bbox_attribute(self.tenant).id, get_bbox_attribute(beta).id
        )

    def test_a_non_bbox_attribute_is_stored_too(self):
        content = THREE_TIER_WITH_BBOX.replace(
            "attr_Bounding Box", "attr_Bounding Box,attr_Population"
        ).replace('-6.9"\n', '-6.9",120\n').replace(
            '-7.5"\n', '-7.5",340\n'
        ).replace('-7.6"\n', '-7.6",560\n')
        self.seed(content, self.tenant)
        population = AdministrationAttribute.objects.get(
            name="Population", tenant=self.tenant
        )
        self.assertEqual(population.type,
                         AdministrationAttribute.Type.VALUE)
        self.assertEqual(
            AdministrationAttributeValue.objects.filter(
                attribute=population
            ).count(),
            3,
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class BundledExampleCsvTestCase(TestCase, CsvSeederMixin):
    """The example seeder.sh imports when its prompt is left blank.

    It is the only hierarchy an operator can get without downloading
    boundary data, so it has to stay importable and has to keep the
    bounding boxes the fake data seeder needs to place a pin.
    """

    EXAMPLE = "./source/administrations/example.csv"

    def test_the_shipped_example_imports(self):
        tenant = self.make_tenant("acme")
        call_command(
            "administration_csv_seeder",
            f"--source={self.EXAMPLE}",
            f"--tenant={tenant.subdomain}",
        )
        levels = Levels.objects.filter(tenant=tenant).order_by("level")
        self.assertEqual(
            [level.name for level in levels],
            ["National", "Province", "District", "Village"],
        )
        self.assertEqual(
            Administration.objects.filter(tenant=tenant).count(), 9
        )

    def test_every_leaf_carries_a_resolvable_bounding_box(self):
        # fake_complete_data_seeder targets the deepest tier only, and
        # refuses to run when none of those units resolves a box.
        tenant = self.make_tenant("acme")
        call_command(
            "administration_csv_seeder",
            f"--source={self.EXAMPLE}",
            f"--tenant={tenant.subdomain}",
        )
        attribute = get_bbox_attribute(tenant)
        self.assertIsNotNone(attribute)
        deepest = Levels.objects.filter(tenant=tenant).order_by("-level")[0]
        leaves = Administration.objects.filter(
            tenant=tenant, level=deepest
        )
        self.assertEqual(leaves.count(), 4)
        for leaf in leaves:
            self.assertIsNotNone(
                resolve_bbox(leaf, attribute, {}),
                f"{leaf.name} has no usable bounding box",
            )
