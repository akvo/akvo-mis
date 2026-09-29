from django.test import TestCase, modify_settings, override_settings

from api.v1.v1_profile.models import Levels
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_users.models import SystemUser, TenantInspection

# One representative write per surface. Each must be refused, and each
# must leave nothing behind.
WRITE_CASES = [
    ("POST", "/api/v1/levels-management", {"name": "x", "level": 9}),
    ("POST", "/api/v1/organisation", {"name": "x"}),
    ("PUT", "/api/v1/update-profile", {"first_name": "x"}),
]


class InspectionReadOnlyMixin(TenantTestHelperMixin):
    def build(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None
        )
        inspection = TenantInspection.objects.create(
            operator=self.operator, tenant=self.acme.tenant,
            code_hash="y" * 64,
        )
        token = TenantInspectionToken.for_inspection(inspection)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def assert_all_writes_refused(self, refused_by):
        """Every write is 403, nothing is written, and the named guard
        is the one that said so.

        `refused_by` is the key the refusal carries: "message" is the
        middleware's JsonResponse, "detail" is DRF rendering the
        authentication class's PermissionDenied. Without it both test
        cases would pass on whichever guard happened to fire first, and
        the point of having two is that either may be bypassed alone.
        """
        before = Levels.objects.count()
        for method, path, payload in WRITE_CASES:
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method.lower())(
                    path, payload, content_type="application/json",
                    HTTP_HOST="acme.app.com", **self.auth,
                )
                self.assertEqual(response.status_code, 403)
                self.assertIn(refused_by, response.json())
        # The half that a status-only assertion would miss: a 403 from
        # the wrong layer, with the row already written, still passes
        # the first check.
        self.assertEqual(Levels.objects.count(), before)


@override_settings(BASE_DOMAIN="app.com")
class InspectionReadOnlyTestCase(TestCase, InspectionReadOnlyMixin):
    """Both guards in place: the normal configuration.

    The middleware runs first and answers, which is what "before any
    view runs" means -- so this asserts its own body, not DRF's.
    """

    def setUp(self):
        self.build()

    def test_every_write_is_refused(self):
        self.assert_all_writes_refused(refused_by="message")

    def test_reads_still_work(self):
        response = self.client.get(
            "/api/v1/profile", HTTP_HOST="acme.app.com", **self.auth
        )
        self.assertEqual(response.status_code, 200)


@override_settings(BASE_DOMAIN="app.com")
@modify_settings(MIDDLEWARE={"remove": "middleware.tenant.TenantMiddleware"})
class InspectionReadOnlyWithoutMiddlewareTestCase(
    TestCase, InspectionReadOnlyMixin
):
    """The authentication guard alone, with the middleware removed.

    Testing the two guards only together proves nothing about either,
    and the entire reason there are two is that one may be bypassed by a
    route the other does not cover.
    """

    def setUp(self):
        self.build()

    def test_every_write_is_still_refused(self):
        self.assert_all_writes_refused(refused_by="detail")
