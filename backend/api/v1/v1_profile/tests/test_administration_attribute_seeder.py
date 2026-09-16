"""Whose attributes does the attribute seeder write, and whose does it wipe?

`AdministrationAttribute` carries a tenant FK -- attributes are a
workspace's own definitions, not install-wide -- but the command scoped
nothing. Three consequences, in ascending order of severity:

1. Attributes were created with tenant=None, so no workspace could see
   them: every read goes through `for_user`, which filters on the tenant.
2. `seed_data` read `AdministrationAttribute.objects.all()` and
   `MobileAssignment.objects.all()`, so it attached workspace A's
   attributes to workspace B's administrations. The resulting
   AdministrationAttributeValue has an `administration` owned by one
   workspace and an `attribute` owned by another, which no later filter
   can untangle.
3. `--clean` deleted every workspace's attributes and values, including
   the "Bounding Box" rows administration_csv_seeder imports and
   fake_complete_data_seeder depends on.
"""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import (
    Administration,
    AdministrationAttribute,
    AdministrationAttributeValue,
    Levels,
)
from api.v1.v1_users.models import Tenant


class AttributeSeederMixin:
    def make_workspace(self, subdomain, depth=2):
        """A workspace with `depth` tiers and one unit per tier."""
        tenant = Tenant.objects.create(subdomain=subdomain)
        parent = None
        for level_index in range(depth):
            level = Levels.objects.create(
                name=f"L{level_index}", level=level_index, tenant=tenant
            )
            parent = Administration.objects.create(
                parent=parent,
                level=level,
                name=f"{subdomain}-{level_index}",
                tenant=tenant,
            )
        return tenant

    def seed(self, **kwargs):
        call_command("administration_attribute_seeder", "--test", True,
                     **kwargs)

    def attributes_of(self, tenant):
        return set(
            AdministrationAttribute.objects.filter(
                tenant=tenant
            ).values_list("name", flat=True)
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class AttributeSeederTenantScopeTest(AttributeSeederMixin, TestCase):
    def setUp(self):
        self.acme = self.make_workspace("acme")
        self.other = self.make_workspace("other")

    def test_attributes_are_stamped_with_the_named_workspace(self):
        self.seed(tenant="acme")

        self.assertEqual(
            self.attributes_of(self.acme),
            {"Population", "Urban or Rural", "Primary Occupations",
             "Education"},
        )
        self.assertEqual(self.attributes_of(self.other), set())
        self.assertEqual(self.attributes_of(None), set())

    def test_values_never_cross_workspaces(self):
        """The sharpest edge: a value row joining two workspaces."""
        self.seed(tenant="acme")
        self.seed(tenant="other")

        for value in AdministrationAttributeValue.objects.all():
            self.assertEqual(
                value.administration.tenant_id,
                value.attribute.tenant_id,
                "attribute and administration must belong to one workspace",
            )

    def test_values_land_on_the_named_workspaces_units(self):
        self.seed(tenant="acme")

        tenants = {
            v.administration.tenant_id
            for v in AdministrationAttributeValue.objects.all()
        }
        self.assertEqual(tenants, {self.acme.id})

    def test_no_tenant_means_the_tenant_less_space(self):
        Levels.objects.create(name="Global", level=0, tenant=None)
        Administration.objects.create(
            parent=None,
            level=Levels.objects.get(name="Global", tenant=None),
            name="Global root",
            tenant=None,
        )

        self.seed()

        self.assertTrue(self.attributes_of(None))
        self.assertEqual(self.attributes_of(self.acme), set())

    def test_unknown_subdomain_is_rejected_before_any_write(self):
        with self.assertRaises(CommandError) as ctx:
            self.seed(tenant="acmee")

        self.assertIn(
            "No workspace with subdomain 'acmee'", str(ctx.exception)
        )
        self.assertEqual(AdministrationAttribute.objects.count(), 0)

    def test_rerunning_creates_no_duplicate_attributes(self):
        self.seed(tenant="acme")
        before = AdministrationAttribute.objects.filter(
            tenant=self.acme
        ).count()

        self.seed(tenant="acme")

        self.assertEqual(
            AdministrationAttribute.objects.filter(tenant=self.acme).count(),
            before,
        )

    def test_deepest_level_is_chosen_by_level_not_id(self):
        """`order_by("-id")` picked the last workspace *configured*.

        Ids ascend across the whole install, so `other`'s level 0 -- made
        after `acme`'s level 1 -- had the higher id. A seed for `acme`
        then found a level belonging to nobody it was asked about.
        """
        self.seed(tenant="acme")

        levels = {
            v.administration.level.level
            for v in AdministrationAttributeValue.objects.all()
        }
        self.assertEqual(levels, {1})

    def test_a_workspace_with_no_levels_is_a_no_op(self):
        empty = Tenant.objects.create(subdomain="empty")

        self.seed(tenant="empty")

        self.assertTrue(self.attributes_of(empty))
        self.assertEqual(AdministrationAttributeValue.objects.count(), 0)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AttributeSeederCleanTest(AttributeSeederMixin, TestCase):
    def setUp(self):
        self.acme = self.make_workspace("acme")
        self.other = self.make_workspace("other")
        self.seed(tenant="acme")
        self.seed(tenant="other")

    def test_clean_removes_only_the_named_workspaces_attributes(self):
        self.seed(tenant="acme", clean=1)

        self.assertEqual(self.attributes_of(self.acme), set())
        self.assertTrue(self.attributes_of(self.other))

    def test_clean_removes_only_the_named_workspaces_values(self):
        self.seed(tenant="acme", clean=1)

        remaining = {
            v.administration.tenant_id
            for v in AdministrationAttributeValue.objects.all()
        }
        self.assertEqual(remaining, {self.other.id})

    def test_clean_leaves_an_imported_attribute_of_another_workspace(self):
        """`Bounding Box` is imported by administration_csv_seeder and the
        data seeder refuses to run without it. An unscoped clean took it."""
        imported = AdministrationAttribute.objects.create(
            name="Bounding Box",
            tenant=self.other,
            type=AdministrationAttribute.Type.VALUE,
        )

        self.seed(tenant="acme", clean=1)

        self.assertTrue(
            AdministrationAttribute.objects.filter(pk=imported.pk).exists()
        )
