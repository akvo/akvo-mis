import json

from django.test import TestCase, override_settings
from django.utils import timezone

from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.models import SystemUser, TenantInspection

ADMIN_HOST = "admin.app.com"


@override_settings(BASE_DOMAIN="app.com")
class InspectionHandoffTestCase(TestCase, TenantTestHelperMixin):
    """The console hands over a code, not a token.

    A JWT in a query string lands in nginx logs, browser history and any
    Referer the page emits, and stays valid there for its whole life. A
    single-use 60-second code bounds that to one use.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        self.auth = self.bearer(self.operator)

    def mint(self):
        return self.client.post(
            f"/api/v1/admin/tenants/{self.acme.tenant.pk}/inspect",
            HTTP_HOST=ADMIN_HOST, **self.auth,
        )

    def exchange(self, code):
        return self.client.post(
            "/api/v1/inspect/exchange",
            json.dumps({"code": code}),
            content_type="application/json",
            HTTP_HOST="acme.app.com",
        )

    def test_mint_records_the_session(self):
        response = self.mint()
        self.assertEqual(response.status_code, 200)
        self.assertIn("code", response.json())
        record = TenantInspection.objects.get()
        self.assertEqual(record.operator_id, self.operator.pk)
        self.assertEqual(record.tenant_id, self.acme.tenant.pk)

    def test_exchange_sets_a_host_only_cookie(self):
        code = self.mint().json()["code"]
        response = self.exchange(code)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies["AUTH_TOKEN"]
        # No domain attribute: the session is confined to this
        # workspace's origin and never reaches the console's.
        self.assertEqual(cookie["domain"], "")

    def test_a_code_works_exactly_once(self):
        code = self.mint().json()["code"]
        self.assertEqual(self.exchange(code).status_code, 200)
        self.assertEqual(self.exchange(code).status_code, 400)

    def test_an_expired_code_is_refused(self):
        code = self.mint().json()["code"]
        record = TenantInspection.objects.get()
        record.created_at = timezone.now() - timezone.timedelta(seconds=120)
        record.save(update_fields=["created_at"])
        self.assertEqual(self.exchange(code).status_code, 400)

    def test_an_unknown_code_is_refused(self):
        self.assertEqual(self.exchange("nope").status_code, 400)

    def test_a_code_is_refused_on_another_workspaces_host(self):
        # The code names a workspace and so does the host. Accepting a
        # mismatch sets a live-looking cookie on the wrong origin: the
        # banner would say "Inspecting beta" while the token carries
        # acme's authority, and every request after it 403s at the host
        # check with nothing on screen to explain why.
        self.create_tenant("beta", ["Country"], "Uganda")
        code = self.mint().json()["code"]
        response = self.client.post(
            "/api/v1/inspect/exchange",
            json.dumps({"code": code}),
            content_type="application/json",
            HTTP_HOST="beta.app.com",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("AUTH_TOKEN", response.cookies)
        # And refusing it must not burn it -- the operator's own tab is
        # still waiting to spend it on the right host.
        self.assertEqual(self.exchange(code).status_code, 200)

    def test_a_workspace_user_cannot_mint(self):
        response = self.client.post(
            f"/api/v1/admin/tenants/{self.acme.tenant.pk}/inspect",
            HTTP_HOST=ADMIN_HOST, **self.bearer(self.acme.admin),
        )
        self.assertEqual(response.status_code, 403)
