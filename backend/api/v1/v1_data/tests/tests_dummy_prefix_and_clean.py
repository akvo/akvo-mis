from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.constants import (
    DUMMY_EMAIL_DOMAIN,
    DUMMY_EMAIL_PREFIX,
    DUMMY_PREFIX,
)
from api.v1.v1_data.management.commands.fake_complete_data_seeder import (
    mark_as_dummy,
)
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.bbox import (
    BboxError,
    get_bbox_attribute,
    parse_bbox,
    random_point_in,
)
from api.v1.v1_profile.constants import BBOX_ATTRIBUTE_NAME, DataAccessTypes
from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttributeValue,
    Levels,
    Role,
)
from api.v1.v1_users.models import Organisation, SystemUser, Tenant

FIJI_BBOX = "177.0,-18.3,180.0,-16.1"


class BboxTest(TestCase):
    """A box is rejected rather than repaired.

    An inverted or out-of-range box is far more likely to be columns swapped
    at generation time than a real place, and a silently corrected one puts
    pins somewhere plausible-looking and wrong.
    """

    def test_parses_four_numbers(self):
        self.assertEqual(
            parse_bbox("177.0,-18.3,180.0,-16.1"),
            (177.0, -18.3, 180.0, -16.1),
        )

    def test_rejects_wrong_arity(self):
        with self.assertRaisesMessage(BboxError, "four numbers"):
            parse_bbox("177.0,-18.3,180.0")

    def test_rejects_non_numeric(self):
        with self.assertRaisesMessage(BboxError, "not four numbers"):
            parse_bbox("a,b,c,d")

    def test_rejects_inverted_box(self):
        with self.assertRaisesMessage(BboxError, "min < max"):
            parse_bbox("180.0,-16.1,177.0,-18.3")

    def test_rejects_out_of_range_latitude(self):
        with self.assertRaisesMessage(BboxError, "latitudes"):
            parse_bbox("177.0,-95.0,180.0,-16.1")

    def test_rejects_empty(self):
        with self.assertRaisesMessage(BboxError, "four numbers"):
            parse_bbox("")

    def test_point_is_inside_the_box_and_lat_first(self):
        bbox = parse_bbox(FIJI_BBOX)
        min_lng, min_lat, max_lng, max_lat = bbox
        for _ in range(50):
            lat, lng = random_point_in(bbox)
            # FormData.geo is [lat, lng]; the map widgets read geo[0] as
            # latitude, so the order is load-bearing.
            self.assertTrue(min_lat <= lat <= max_lat)
            self.assertTrue(min_lng <= lng <= max_lng)


class MarkAsDummyTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

    def make_form_data(self, name):
        user = SystemUser.objects.create_user(
            email="someone@test.com", first_name="A", last_name="B",
        )
        return FormData.objects.create(
            name=name,
            form=Forms.objects.filter(parent__isnull=True).first(),
            administration=Administration.objects.filter(
                parent__isnull=False
            ).first(),
            created_by=user,
            geo=[0, 0],
        )

    def test_applies_the_prefix(self):
        data = mark_as_dummy(self.make_form_data("Village survey"))
        self.assertEqual(data.name, f"{DUMMY_PREFIX}Village survey")

    def test_is_idempotent(self):
        data = mark_as_dummy(self.make_form_data("Village survey"))
        data = mark_as_dummy(data)
        self.assertEqual(data.name, f"{DUMMY_PREFIX}Village survey")
        self.assertNotIn(f"{DUMMY_PREFIX}{DUMMY_PREFIX}", data.name)

    def test_persists_to_the_database(self):
        data = mark_as_dummy(self.make_form_data("Village survey"))
        data.refresh_from_db()
        self.assertTrue(data.name.startswith(DUMMY_PREFIX))


class SeederTestModeMixin:
    """--test drives the bundled fixture and is exempt from tenant/bbox."""

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

    def seed(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()


@override_settings(USE_TZ=False, TEST_ENV=True)
class PrefixTest(SeederTestModeMixin, TestCase):
    def test_every_generated_datapoint_is_prefixed(self):
        self.seed("-r", 3)
        self.assertTrue(FormData.objects.exists())
        for data in FormData.objects_with_deleted.all():
            self.assertTrue(
                data.name.startswith(DUMMY_PREFIX),
                f"{data.name} is not marked",
            )

    def test_prefix_survives_add_fake_answers(self):
        # add_fake_answers rebuilds `name` from the form's meta questions,
        # so a prefix applied at create() is discarded. Every seeded form
        # has at least one meta question, which is what makes this the
        # regression that matters.
        self.seed("-r", 2)
        meta_named = FormData.objects.filter(parent__isnull=True)
        self.assertTrue(meta_named.exists())
        for data in meta_named:
            self.assertTrue(data.name.startswith(DUMMY_PREFIX))

    def test_monitoring_children_are_prefixed(self):
        self.seed("-r", 2, "-m", 2)
        children = FormData.objects.filter(parent__isnull=False)
        self.assertTrue(children.exists())
        for child in children:
            self.assertTrue(child.name.startswith(DUMMY_PREFIX))

    def test_drafts_are_prefixed(self):
        self.seed("-r", 4, "--draft=true", "--approved=false")
        drafts = FormData.objects_draft.all()
        self.assertTrue(drafts.exists())
        for draft in drafts:
            self.assertTrue(draft.name.startswith(DUMMY_PREFIX))

    def test_generated_accounts_are_namespaced(self):
        self.seed("-r", 2)
        seeded = SystemUser.objects.filter(
            email__startswith=DUMMY_EMAIL_PREFIX
        )
        self.assertTrue(seeded.exists())
        for user in seeded:
            self.assertTrue(user.email.endswith(DUMMY_EMAIL_DOMAIN))

    def test_mobile_assignments_are_prefixed(self):
        self.seed("-r", 2)
        assignments = MobileAssignment.objects.all()
        self.assertTrue(assignments.exists())
        for assignment in assignments:
            self.assertTrue(assignment.name.startswith(DUMMY_PREFIX))


@override_settings(USE_TZ=False, TEST_ENV=True, DEBUG=True)
class CleanTest(SeederTestModeMixin, TestCase):
    def test_clean_removes_datapoints_and_cascades_answers(self):
        self.seed("-r", 3, "-m", 2)
        self.assertTrue(Answers.objects.exists())

        self.seed("--clean=true")

        self.assertEqual(FormData.objects_with_deleted.count(), 0)
        self.assertEqual(Answers.objects.count(), 0)

    def test_clean_removes_drafts(self):
        self.seed("-r", 4, "--draft=true", "--approved=false")
        self.assertTrue(FormData.objects_draft.exists())
        self.seed("--clean=true")
        self.assertEqual(FormData.objects_draft.count(), 0)

    def test_clean_collects_soft_deleted_rows(self):
        # The default manager hides soft-deleted rows, so a --clean built
        # on it would leave them behind forever.
        self.seed("-r", 3)
        FormData.objects.all()[:1][0].delete()
        self.assertTrue(FormData.objects_deleted.exists())

        self.seed("--clean=true")
        self.assertEqual(FormData.objects_with_deleted.count(), 0)

    def test_clean_is_idempotent(self):
        self.seed("-r", 2)
        self.seed("--clean=true")
        self.seed("--clean=true")
        self.assertEqual(FormData.objects_with_deleted.count(), 0)

    def test_clean_then_reseed_does_not_double(self):
        # Reset is two runs now: --clean is terminal and seeds nothing.
        self.seed("-r", 3)
        first = FormData.objects.count()
        self.seed("--clean=true")
        self.assertEqual(FormData.objects.count(), 0)
        self.seed("-r", 3)
        self.assertEqual(FormData.objects.count(), first)

    def test_clean_seeds_nothing(self):
        self.seed("-r", 3)
        self.seed("--clean=true")
        self.assertEqual(FormData.objects_with_deleted.count(), 0)

    def test_clean_removes_seeded_accounts(self):
        self.seed("-r", 2)
        self.seed("--clean=true")
        self.assertEqual(
            SystemUser.objects_with_deleted.filter(
                email__startswith=DUMMY_EMAIL_PREFIX
            ).count(),
            0,
        )

    def test_clean_removes_mobile_assignments(self):
        self.seed("-r", 2)
        self.seed("--clean=true")
        self.assertEqual(MobileAssignment.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_clean_is_refused_when_debug_is_false(self):
        self.seed("-r", 2)
        before = FormData.objects.count()
        with self.assertRaisesMessage(CommandError, "DEBUG=False"):
            self.seed("--clean=true")
        self.assertEqual(FormData.objects.count(), before)


@override_settings(USE_TZ=False, TEST_ENV=True, DEBUG=True)
class CleanPreservesRealDataTest(SeederTestModeMixin, TestCase):
    """The sharp edge: the seeder reuses existing submitters.

    On a shared workspace that reused account belongs to a real person, so
    a --clean keyed on `created_by` would cascade away their genuine
    submissions. The delete key is the prefix for exactly this reason.
    """

    def test_real_data_from_a_reused_user_survives_clean(self):
        self.seed("-r", 2)

        # A real submitter the seeder is free to pick up, holding a real
        # datapoint that carries no prefix.
        reused = SystemUser.objects.filter(
            email__startswith=DUMMY_EMAIL_PREFIX
        ).first()
        self.assertIsNotNone(reused)
        real_row = FormData.objects.create(
            name="Real village survey",
            form=Forms.objects.filter(parent__isnull=True).first(),
            administration=Administration.objects.filter(
                parent__isnull=False
            ).first(),
            created_by=reused,
            geo=[0, 0],
        )

        self.seed("--clean=true")

        real_row.refresh_from_db()
        self.assertIsNone(real_row.deleted_at)
        self.assertEqual(real_row.name, "Real village survey")
        # The account is kept too, because it still owns a live datapoint.
        self.assertTrue(
            SystemUser.objects_with_deleted.filter(pk=reused.pk).exists()
        )

    def test_unprefixed_rows_from_another_author_survive(self):
        self.seed("-r", 2)
        author = SystemUser.objects.create_user(
            email="real.person@ministry.gov",
            first_name="Real", last_name="Person",
        )
        keeper = FormData.objects.create(
            name="Genuine submission",
            form=Forms.objects.filter(parent__isnull=True).first(),
            administration=Administration.objects.filter(
                parent__isnull=False
            ).first(),
            created_by=author,
            geo=[0, 0],
        )

        self.seed("--clean=true")

        keeper.refresh_from_db()
        self.assertEqual(keeper.name, "Genuine submission")


@override_settings(USE_TZ=False, TEST_ENV=True)
class ApprovedOnlyTest(SeederTestModeMixin, TestCase):
    """The default run is approved-only; the contradiction is an error."""

    def test_default_run_has_no_pending_no_draft_no_approvers(self):
        self.seed("-r", 3)
        self.assertEqual(
            FormData.objects.filter(is_pending=True).count(), 0
        )
        self.assertEqual(FormData.objects_draft.count(), 0)
        self.assertEqual(
            SystemUser.objects.filter(
                email__startswith=f"{DUMMY_EMAIL_PREFIX}approver"
            ).count(),
            0,
        )

    def test_approved_true_with_draft_true_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "contradicts"):
            self.seed("-r", 2, "--draft=true")

    def test_approved_false_produces_pending_rows(self):
        self.seed("-r", 4, "--approved=false")
        self.assertTrue(
            FormData.objects.filter(is_pending=True).exists()
        )


class RequiredArgumentsTest(TestCase):
    """Outside --test the workspace must be named, and must have geography."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test")

    def seed(self, *args):
        call_command(
            "fake_complete_data_seeder",
            *args,
            stdout=StringIO(),
            stderr=StringIO(),
        )

    def test_tenant_is_required_without_test(self):
        with self.assertRaisesMessage(CommandError, "--tenant is required"):
            self.seed("-r", 1)

    def test_unknown_tenant_is_rejected(self):
        Tenant.objects.create(subdomain="acme")
        with self.assertRaisesMessage(CommandError, "No workspace with"):
            self.seed("-r", 1, "--tenant", "ghost")

    def test_bbox_argument_no_longer_exists(self):
        # Coordinates come from the hierarchy now. A leftover --bbox in a
        # script must fail loudly rather than be silently ignored.
        Tenant.objects.create(subdomain="acme")
        with self.assertRaises(CommandError):
            self.seed("-r", 1, "--tenant", "acme", "--bbox", FIJI_BBOX)

    def test_workspace_without_a_hierarchy_is_rejected(self):
        tenant = Tenant.objects.create(subdomain="acme")
        level = Levels.objects.create(name="National", level=0,
                                      tenant=tenant)
        Administration.objects.create(
            parent=None, level=level, name="Acme", tenant=tenant
        )
        with self.assertRaisesMessage(
            CommandError, "administration_csv_seeder"
        ):
            self.seed("-r", 1, "--tenant", "acme")

    @override_settings(DEBUG=True)
    def test_clean_needs_only_a_tenant(self):
        # A clean generates no points, so it must not be blocked by the
        # geography checks that seeding needs.
        Tenant.objects.create(subdomain="acme")
        self.seed("--tenant", "acme", "--clean=true")

    def test_test_mode_needs_no_tenant(self):
        # The 34 existing callers rely on this exemption, and TEST_GEO_DATA
        # carries its own coordinates.
        self.seed("-r", 1, "--test=true")
        self.assertTrue(FormData.objects.exists())
        self.assertTrue(
            all(row.geo for row in FormData.objects.all())
        )


class TenantWorkspaceMixin:
    """A workspace shaped like one built through registration.

    The bundled seeders are not tenant-aware, so their rows are adopted
    into the tenant here rather than reimplemented.
    """

    def make_workspace(self, subdomain, with_hierarchy=False):
        tenant = Tenant.objects.create(subdomain=subdomain)
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test")

        Forms.objects.filter(tenant__isnull=True).update(tenant=tenant)
        Role.objects.filter(tenant__isnull=True).update(tenant=tenant)
        Organisation.objects.filter(tenant__isnull=True).update(
            tenant=tenant
        )
        Levels.objects.filter(tenant__isnull=True).update(tenant=tenant)
        if not with_hierarchy:
            # Only the root survives: the state configure_project leaves.
            # Deepest level first -- Administration.parent is PROTECT, so a
            # parent cannot go before its children.
            non_root = Administration.objects.filter(parent__isnull=False)
            depths = sorted(
                non_root.values_list(
                    "level__level", flat=True
                ).distinct(),
                reverse=True,
            )
            for depth in depths:
                non_root.filter(level__level=depth).delete()
            Levels.objects.filter(level__gt=0).delete()
        Administration.objects.filter(tenant__isnull=True).update(
            tenant=tenant
        )
        return tenant

    def attach_bboxes(self, tenant):
        """A distinct box per unit, so a pin can be traced back to one.

        Deliberately not one shared box: a shared box would pass even if the
        seeder ignored the administration entirely, which is the bug this
        feature exists to fix.
        """
        attribute = get_bbox_attribute(tenant, create=True)
        boxes = {}
        units = Administration.objects.filter(
            tenant=tenant, parent__isnull=False
        ).order_by("id")
        for offset, unit in enumerate(units):
            min_lng = 170.0 + offset * 0.5
            min_lat = -18.0 + offset * 0.5
            raw = (
                f"{min_lng},{min_lat},{min_lng + 0.1},{min_lat + 0.1}"
            )
            AdministrationAttributeValue.objects.create(
                administration=unit,
                attribute=attribute,
                value={"value": raw},
            )
            boxes[unit.id] = parse_bbox(raw)
        return attribute, boxes

    def seed(self, tenant, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--tenant", tenant.subdomain,
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()


@override_settings(USE_TZ=False, TEST_ENV=True, DEBUG=True)
class GeoFromHierarchyTest(TenantWorkspaceMixin, TestCase):
    """Every generated pin comes from its own unit's bounding box."""

    def test_every_row_has_a_geo(self):
        tenant = self.make_workspace("acme", with_hierarchy=True)
        self.attach_bboxes(tenant)
        self.seed(tenant, "-r", 3)
        rows = FormData.objects.filter(form__tenant=tenant)
        self.assertTrue(rows.exists())
        self.assertFalse(rows.filter(geo__isnull=True).exists())

    def test_pin_falls_inside_its_own_administrations_box(self):
        # The whole point of SEED-003. Each unit has a different box, so a
        # seeder that ignored the administration would land outside.
        tenant = self.make_workspace("acme", with_hierarchy=True)
        _attribute, boxes = self.attach_bboxes(tenant)
        self.seed(tenant, "-r", 4)
        rows = FormData.objects.filter(form__tenant=tenant)
        self.assertTrue(rows.exists())
        for row in rows:
            min_lng, min_lat, max_lng, max_lat = boxes[row.administration_id]
            lat, lng = row.geo
            self.assertTrue(
                min_lat <= lat <= max_lat and min_lng <= lng <= max_lng,
                f"{row.name!r} at {row.geo} is outside the box of "
                f"{row.administration.name}",
            )

    def test_monitoring_children_inherit_the_parents_pin(self):
        tenant = self.make_workspace("acme", with_hierarchy=True)
        _attribute, boxes = self.attach_bboxes(tenant)
        self.seed(tenant, "-r", 2)
        for row in FormData.objects.filter(
            form__tenant=tenant, parent__isnull=False
        ):
            self.assertEqual(row.geo, row.parent.geo)

    def test_pins_are_not_all_identical(self):
        # A box scatters; a stored point would stack every datapoint in a
        # unit on one pixel, which is why D-1 stores a box.
        tenant = self.make_workspace("acme", with_hierarchy=True)
        self.attach_bboxes(tenant)
        self.seed(tenant, "-r", 6)
        pins = {
            tuple(row.geo)
            for row in FormData.objects.filter(form__tenant=tenant)
        }
        self.assertGreater(len(pins), 1)

    def test_ancestor_box_is_used_when_the_leaf_has_none(self):
        # Boxes are attached to the deepest unit of a CSV row (D-6), so a
        # workspace that later gains a tier has targets below the boxes.
        tenant = self.make_workspace("acme", with_hierarchy=True)
        attribute = get_bbox_attribute(tenant, create=True)
        deepest = Administration.objects.filter(
            tenant=tenant, parent__isnull=False
        ).order_by("-level__level").first().level.level
        raw = "170.0,-18.0,170.5,-17.5"
        for unit in Administration.objects.filter(
            tenant=tenant, parent__isnull=False
        ).exclude(level__level=deepest):
            AdministrationAttributeValue.objects.create(
                administration=unit, attribute=attribute,
                value={"value": raw},
            )
        self.seed(tenant, "-r", 2)
        min_lng, min_lat, max_lng, max_lat = parse_bbox(raw)
        rows = FormData.objects.filter(form__tenant=tenant)
        self.assertTrue(rows.exists())
        for row in rows:
            lat, lng = row.geo
            self.assertTrue(min_lat <= lat <= max_lat)
            self.assertTrue(min_lng <= lng <= max_lng)

    def test_a_corrupt_box_falls_through_instead_of_crashing(self):
        # Attributes are editable in the UI (D-3/Q2), so nonsense can
        # arrive. It must degrade to the ancestor, not fail the run.
        tenant = self.make_workspace("acme", with_hierarchy=True)
        attribute = get_bbox_attribute(tenant, create=True)
        units = list(
            Administration.objects.filter(
                tenant=tenant, parent__isnull=False
            ).order_by("level__level")
        )
        for unit in units:
            raw = (
                "not a box" if unit is units[-1]
                else "170.0,-18.0,170.5,-17.5"
            )
            AdministrationAttributeValue.objects.create(
                administration=unit, attribute=attribute,
                value={"value": raw},
            )
        self.seed(tenant, "-r", 2)
        self.assertTrue(
            FormData.objects.filter(form__tenant=tenant).exists()
        )

    def test_seeding_without_any_box_is_refused(self):
        tenant = self.make_workspace("acme", with_hierarchy=True)
        with self.assertRaisesMessage(
            CommandError, BBOX_ATTRIBUTE_NAME
        ):
            self.seed(tenant, "-r", 2)
        self.assertFalse(
            FormData.objects.filter(form__tenant=tenant).exists()
        )

    def test_workspace_with_only_a_root_is_refused(self):
        # This is where ensure_hierarchy used to invent a throwaway tree.
        # It could only ever produce datapoints without coordinates.
        tenant = self.make_workspace("acme")
        with self.assertRaisesMessage(
            CommandError, "administration_csv_seeder"
        ):
            self.seed(tenant, "-r", 2)

    def test_clean_keeps_the_boxes(self):
        # Boxes belong to the hierarchy, not to the generated data, and
        # carry no DUMMY- prefix -- so a clean must leave them behind.
        tenant = self.make_workspace("acme", with_hierarchy=True)
        self.attach_bboxes(tenant)
        before = AdministrationAttributeValue.objects.count()
        self.seed(tenant, "-r", 2)
        self.seed(tenant, "--clean=true")
        self.assertEqual(
            AdministrationAttributeValue.objects.count(), before
        )
        self.assertIsNotNone(get_bbox_attribute(tenant))

    def test_clean_keeps_a_real_hierarchy(self):
        tenant = self.make_workspace("beta", with_hierarchy=True)
        self.attach_bboxes(tenant)
        before = Administration.objects.filter(tenant=tenant).count()
        self.seed(tenant, "-r", 2)
        self.seed(tenant, "--clean=true")
        self.assertEqual(
            Administration.objects.filter(tenant=tenant).count(), before
        )


@override_settings(USE_TZ=False, TEST_ENV=True, DEBUG=True)
class CleanTenantScopeTest(TenantWorkspaceMixin, TestCase):
    def make_bare_workspace(self, subdomain):
        """A second workspace with definitions of its very own.

        Nothing may be shared with the first: FormData's tenant is derived
        through `form__tenant`, so handing one Forms row to two tenants
        would silently move the first tenant's data.
        """
        tenant = Tenant.objects.create(subdomain=subdomain)
        level = Levels.objects.create(
            name="National", level=0, tenant=tenant
        )
        root = Administration.objects.create(
            parent=None, level=level, name=subdomain, tenant=tenant
        )
        # A child tier, because datapoints only ever attach below the root.
        child_level = Levels.objects.create(
            name="Province", level=1, tenant=tenant
        )
        Administration.objects.create(
            parent=root, level=child_level, name=f"{subdomain} province",
            tenant=tenant,
        )
        role = Role.objects.create(
            name=f"{subdomain} submitter", administration_level=level
        )
        role.role_role_access.create(data_access=DataAccessTypes.submit)
        Forms.objects.create(name=f"{subdomain} form", tenant=tenant)
        Organisation.objects.create(name=f"{subdomain} org", tenant=tenant)
        self.attach_bboxes(tenant)
        return tenant

    def test_clean_leaves_another_workspace_alone(self):
        acme = self.make_workspace("acme", with_hierarchy=True)
        self.attach_bboxes(acme)
        beta = self.make_bare_workspace("beta")

        self.seed(acme, "-r", 2)
        self.seed(beta, "-r", 2)
        beta_rows = FormData.objects.filter(form__tenant=beta).count()
        self.assertTrue(beta_rows)

        # Cleaning acme must not touch beta's rows.
        self.seed(acme, "--clean=true")
        self.assertEqual(
            FormData.objects.filter(form__tenant=beta).count(), beta_rows
        )
        self.assertEqual(
            FormData.objects.filter(form__tenant=acme).count(), 0
        )
