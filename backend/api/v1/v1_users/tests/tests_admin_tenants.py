import json

from django.test import TestCase, override_settings

from api.v1.v1_profile.constants import FeatureFlags
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser, Tenant

ADMIN_HOST = "admin.app.com"
TENANTS = "/api/v1/admin/tenants"
# The list itself. `TENANTS` stays as the prefix the detail routes
# hang off -- deactivate, activate and delete are untouched.
SUMMARY = TENANTS + "/summary"


@override_settings(BASE_DOMAIN="app.com")
class AdminTenantsTestCase(TestCase, TenantTestHelperMixin):
    """The console reads every workspace, and only operators reach it.

    These endpoints query Tenant.objects directly rather than through
    for_user(). The bypass is visible in each view on purpose: an
    operator is tenant-less, so for_user would filter on tenant IS NULL
    and return nothing at all.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.beta = self.create_tenant("beta", ["Country"], "Uganda")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)

    def get(self, path):
        return self.client.get(path, HTTP_HOST=ADMIN_HOST, **self.auth)

    def post(self, path):
        return self.client.post(path, HTTP_HOST=ADMIN_HOST, **self.auth)

    def test_lists_every_workspace(self):
        response = self.get(SUMMARY)
        self.assertEqual(response.status_code, 200)
        subdomains = [row["subdomain"] for row in response.json()["data"]]
        # Both, plus the `default` row the tenant backfill migration
        # leaves behind. Seeing a workspace the operator has no
        # membership of is the whole point -- for_user() would have
        # returned nothing at all.
        self.assertIn("acme", subdomains)
        self.assertIn("beta", subdomains)

    def test_carries_the_root_unit_name(self):
        rows = {
            row["subdomain"]: row
            for row in self.get(SUMMARY).json()["data"]
        }
        self.assertEqual(rows["acme"]["name"], "Kenya")

    def test_a_workspace_user_is_refused(self):
        response = self.client.get(
            SUMMARY, HTTP_HOST=ADMIN_HOST,
            **self.bearer(self.acme.admin)
        )
        self.assertEqual(response.status_code, 403)

    def test_an_anonymous_caller_is_refused(self):
        response = self.client.get(SUMMARY, HTTP_HOST=ADMIN_HOST)
        self.assertIn(response.status_code, (401, 403))

    def test_deactivate_then_activate(self):
        pk = self.acme.tenant.pk
        self.assertEqual(self.post(f"{TENANTS}/{pk}/deactivate").status_code,
                         200)
        self.acme.tenant.refresh_from_db()
        self.assertFalse(self.acme.tenant.is_active)
        self.assertEqual(self.post(f"{TENANTS}/{pk}/activate").status_code,
                         200)
        self.acme.tenant.refresh_from_db()
        self.assertTrue(self.acme.tenant.is_active)

    def test_delete_is_soft(self):
        pk = self.acme.tenant.pk
        response = self.client.delete(
            f"{TENANTS}/{pk}", HTTP_HOST=ADMIN_HOST, **self.auth
        )
        self.assertEqual(response.status_code, 200)
        self.acme.tenant.refresh_from_db()
        self.assertIsNotNone(self.acme.tenant.deleted_at)
        # The row survives, because every tenant FK is PROTECT and the
        # data it owns is retained.
        self.assertTrue(Tenant.objects.filter(pk=pk).exists())

    def test_state_reflects_the_columns(self):
        self.post(f"{TENANTS}/{self.beta.tenant.pk}/deactivate")
        rows = {
            row["subdomain"]: row
            for row in self.get(SUMMARY).json()["data"]
        }
        self.assertEqual(rows["acme"]["state"], "active")
        self.assertEqual(rows["beta"]["state"], "suspended")

    def test_search_narrows_by_subdomain(self):
        rows = self.get(f"{SUMMARY}?search=acm").json()["data"]
        subdomains = [row["subdomain"] for row in rows]
        self.assertEqual(subdomains, ["acme"])

    def test_every_state_round_trips_through_the_filter(self):
        """Filtering by a state returns exactly the rows reporting it.

        `get_state` maps a row to a name and the view maps a name back
        to a queryset. They are inverses written in two places, so this
        asserts they agree rather than trusting them to. A mapping that
        drifts shows up here as a row whose `state` is not the one
        asked for.
        """
        self.post(f"{TENANTS}/{self.beta.tenant.pk}/deactivate")
        self.client.delete(
            f"{TENANTS}/{self.acme.tenant.pk}", HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        expected = {
            "active": None,
            "suspended": "beta",
            "deleted": "acme",
        }
        for state, present in expected.items():
            with self.subTest(state=state):
                rows = self.get(
                    f"{SUMMARY}?state={state}"
                ).json()["data"]
                self.assertTrue(rows, f"no workspace reported {state}")
                for row in rows:
                    self.assertEqual(row["state"], state)
                if present:
                    self.assertIn(
                        present, [row["subdomain"] for row in rows]
                    )

    def test_a_deleted_workspace_is_deleted_however_it_got_there(self):
        # Deletion is an ending: suspending first must not move a
        # workspace out of `deleted` into `suspended`.
        pk = self.acme.tenant.pk
        self.post(f"{TENANTS}/{pk}/deactivate")
        self.client.delete(
            f"{TENANTS}/{pk}", HTTP_HOST=ADMIN_HOST, **self.auth
        )
        suspended = [
            row["subdomain"]
            for row in self.get(
                f"{SUMMARY}?state=suspended"
            ).json()["data"]
        ]
        deleted = [
            row["subdomain"]
            for row in self.get(
                f"{SUMMARY}?state=deleted"
            ).json()["data"]
        ]
        self.assertNotIn("acme", suspended)
        self.assertIn("acme", deleted)

    def test_an_unknown_state_is_refused(self):
        # Ignoring it would read as "this deployment has none of those".
        response = self.get(f"{SUMMARY}?state=archived")
        self.assertEqual(response.status_code, 400)

    def test_toggles_a_feature(self):
        pk = self.acme.tenant.pk
        response = self.client.put(
            f"{TENANTS}/{pk}/features",
            json.dumps({FeatureFlags.embedded_dashboard: True}),
            content_type="application/json",
            HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.acme.tenant.refresh_from_db()
        self.assertTrue(
            self.acme.tenant.features[FeatureFlags.embedded_dashboard]
        )

    def test_rejects_an_unknown_feature_key(self):
        response = self.client.put(
            f"{TENANTS}/{self.acme.tenant.pk}/features",
            json.dumps({"embeded_dashboard": True}),  # typo on purpose
            content_type="application/json",
            HTTP_HOST=ADMIN_HOST,
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)
