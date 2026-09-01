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
    parse_bbox,
    random_point_in,
)
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_profile.models import Administration, Levels, Role
from api.v1.v1_users.models import Organisation, SystemUser, Tenant

FIJI_BBOX = "177.0,-18.3,180.0,-16.1"


class BboxTest(TestCase):
    """There is deliberately no default bbox; a bad one must not seed."""

    def test_parses_four_numbers(self):
        self.assertEqual(
            parse_bbox("177.0,-18.3,180.0,-16.1"),
            (177.0, -18.3, 180.0, -16.1),
        )

    def test_rejects_wrong_arity(self):
        with self.assertRaisesMessage(CommandError, "minLng,minLat"):
            parse_bbox("177.0,-18.3,180.0")

    def test_rejects_non_numeric(self):
        with self.assertRaisesMessage(CommandError, "not four numbers"):
            parse_bbox("a,b,c,d")

    def test_rejects_inverted_box(self):
        with self.assertRaisesMessage(CommandError, "min < max"):
            parse_bbox("180.0,-16.1,177.0,-18.3")

    def test_rejects_out_of_range_latitude(self):
        with self.assertRaisesMessage(CommandError, "latitudes"):
            parse_bbox("177.0,-95.0,180.0,-16.1")

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
    """Outside --test, the workspace and the bbox must both be named."""

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
            self.seed("-r", 1, "--bbox", FIJI_BBOX)

    def test_unknown_tenant_is_rejected(self):
        Tenant.objects.create(subdomain="acme")
        with self.assertRaisesMessage(CommandError, "No workspace with"):
            self.seed("-r", 1, "--tenant", "ghost", "--bbox", FIJI_BBOX)

    def test_bbox_is_required_without_test(self):
        Tenant.objects.create(subdomain="acme")
        with self.assertRaisesMessage(CommandError, "--bbox is required"):
            self.seed("-r", 1, "--tenant", "acme")

    @override_settings(DEBUG=True)
    def test_clean_needs_no_bbox(self):
        # A clean generates no points, so demanding a bounding box for it
        # was pure friction.
        Tenant.objects.create(subdomain="acme")
        self.seed("--tenant", "acme", "--clean=true")

    def test_test_mode_needs_neither(self):
        # The 34 existing callers rely on this exemption.
        self.seed("-r", 1, "--test=true")
        self.assertTrue(FormData.objects.exists())


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

    def seed(self, tenant, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--tenant", tenant.subdomain,
            "--bbox", FIJI_BBOX,
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()


@override_settings(USE_TZ=False, TEST_ENV=True, DEBUG=True)
class GeneratedHierarchyTest(TenantWorkspaceMixin, TestCase):
    """A freshly-registered workspace has a root and nothing below it."""

    def test_generates_a_throwaway_hierarchy(self):
        tenant = self.make_workspace("acme")
        self.seed(tenant, "-r", 2, "--depth", 2, "--fanout", 4)

        generated = Administration.objects.filter(
            tenant=tenant, name__startswith=DUMMY_PREFIX
        )
        # depth 2, fanout 4 -> 4 + 16
        self.assertEqual(generated.count(), 20)
        deepest = generated.filter(level__level=2)
        self.assertEqual(deepest.count(), 16)

    def test_generated_units_have_a_path(self):
        # `path` is what every visualization administration filter reads.
        tenant = self.make_workspace("acme")
        self.seed(tenant, "-r", 2, "--depth", 2, "--fanout", 2)
        for unit in Administration.objects.filter(
            tenant=tenant, name__startswith=DUMMY_PREFIX
        ):
            self.assertTrue(unit.path)

    def test_generated_levels_are_prefixed(self):
        tenant = self.make_workspace("acme")
        self.seed(tenant, "-r", 1, "--depth", 2, "--fanout", 2)
        generated = Levels.objects.filter(
            tenant=tenant, name__startswith=DUMMY_PREFIX
        )
        self.assertEqual(generated.count(), 2)

    def test_existing_hierarchy_is_reused_not_regenerated(self):
        tenant = self.make_workspace("beta", with_hierarchy=True)
        self.seed(tenant, "-r", 2)
        self.assertEqual(
            Administration.objects.filter(
                tenant=tenant, name__startswith=DUMMY_PREFIX
            ).count(),
            0,
        )

    def test_geo_points_land_inside_the_bbox(self):
        tenant = self.make_workspace("acme")
        self.seed(tenant, "-r", 3)
        min_lng, min_lat, max_lng, max_lat = parse_bbox(FIJI_BBOX)
        rows = FormData.objects.filter(geo__isnull=False)
        self.assertTrue(rows.exists())
        for row in rows:
            lat, lng = row.geo
            self.assertTrue(min_lat <= lat <= max_lat)
            self.assertTrue(min_lng <= lng <= max_lng)

    def test_clean_removes_generated_units_and_levels(self):
        tenant = self.make_workspace("acme")
        self.seed(tenant, "-r", 2, "--depth", 2, "--fanout", 2)
        self.assertTrue(
            Administration.objects.filter(
                tenant=tenant, name__startswith=DUMMY_PREFIX
            ).exists()
        )

        self.seed(tenant, "--clean=true")

        self.assertEqual(
            Administration.objects.filter(
                tenant=tenant, name__startswith=DUMMY_PREFIX
            ).count(),
            0,
        )
        self.assertEqual(
            Levels.objects.filter(
                tenant=tenant, name__startswith=DUMMY_PREFIX
            ).count(),
            0,
        )
        # The real root and its level survive.
        self.assertTrue(
            Administration.objects.filter(
                tenant=tenant, parent__isnull=True
            ).exists()
        )

    def test_clean_keeps_a_real_hierarchy(self):
        tenant = self.make_workspace("beta", with_hierarchy=True)
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
        Administration.objects.create(
            parent=None, level=level, name=subdomain, tenant=tenant
        )
        role = Role.objects.create(
            name=f"{subdomain} submitter", administration_level=level
        )
        role.role_role_access.create(data_access=DataAccessTypes.submit)
        Forms.objects.create(name=f"{subdomain} form", tenant=tenant)
        Organisation.objects.create(name=f"{subdomain} org", tenant=tenant)
        return tenant

    def test_clean_leaves_another_workspace_alone(self):
        acme = self.make_workspace("acme", with_hierarchy=True)
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
