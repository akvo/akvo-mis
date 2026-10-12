from io import BytesIO

from django.test import TestCase, modify_settings, override_settings

from api.v1.v1_profile.models import Levels
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin
from api.v1.v1_users.authentication import TenantInspectionToken
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_users.models import Organisation, SystemUser, TenantInspection

# One representative write per method the API actually offers, plus the
# two shapes a method test alone would miss: a multipart upload, and a
# GET that writes.
#
# PATCH has no endpoint anywhere in this API. It is here anyway, because
# the guard must refuse before the view gets to decide the method is
# unsupported -- a 405 would mean the request reached the view.
WRITE_CASES = [
    ("POST", "/api/v1/levels-management", {"name": "x", "level": 9}),
    ("POST", "/api/v1/organisation", {"name": "x"}),
    ("PUT", "/api/v1/update-profile", {"first_name": "x"}),
    ("PUT", "/api/v1/levels-management/1", {"name": "x", "level": 9}),
    ("PATCH", "/api/v1/levels-management/1", {"name": "x"}),
    ("DELETE", "/api/v1/levels-management/1", {}),
    ("DELETE", "/api/v1/user/1", {}),
]

# Refused whatever the method, because they write on a GET: each queues
# a Jobs row and a django_q task. A guard that keys only on the method
# lets a "read-only" session create rows and buy worker time until
# someone notices.
MUTATING_GETS = [
    "/api/v1/download/generate?form_id=1&type=all",
    "/api/v1/download/datapoint-report?form_id=1",
]


class InspectionReadOnlyMixin(TenantTestHelperMixin):
    def build(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.operator = SystemUser.objects.create(
            email="ops@akvo.org", is_platform_admin=True, tenant=None,
            first_name="Ops",
        )
        inspection = TenantInspection.objects.create(
            operator=self.operator, tenant=self.acme.tenant,
            code_hash="y" * 64,
        )
        token = TenantInspectionToken.for_inspection(inspection)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def counts(self):
        """Everything a refused request might have created or removed.

        Counted around every case rather than only around the one that
        writes Levels: a 403 from the wrong layer, with the row already
        written, passes a status-only assertion.
        """
        return {
            "levels": Levels.objects.count(),
            "organisations": Organisation.objects.count(),
            "users": SystemUser.objects.count(),
            "jobs": Jobs.objects.count(),
        }

    def assert_all_writes_refused(self, refused_by):
        """Every write is 403, nothing is written, and the named guard
        is the one that said so.

        `refused_by` is the key the refusal carries: "message" is the
        middleware's JsonResponse, "detail" is DRF rendering the
        authentication class's PermissionDenied. Without it both test
        cases would pass on whichever guard happened to fire first, and
        the point of having two is that either may be bypassed alone.
        """
        before = self.counts()
        name = self.operator.first_name
        for method, path, payload in WRITE_CASES:
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method.lower())(
                    path, payload, content_type="application/json",
                    HTTP_HOST="acme.app.com", **self.auth,
                )
                self.assertEqual(response.status_code, 403)
                self.assertIn(refused_by, response.json())
        for path in MUTATING_GETS:
            with self.subTest(path=path, method="GET"):
                response = self.client.get(
                    path, HTTP_HOST="acme.app.com", **self.auth
                )
                self.assertEqual(response.status_code, 403)
                self.assertIn(refused_by, response.json())
        with self.subTest(path="/api/v1/upload/images", method="POST"):
            # Multipart, because the guards see a request rather than a
            # parsed body and nothing about them should depend on the
            # content type -- but nothing proves that until one runs.
            response = self.client.post(
                "/api/v1/upload/images",
                {"file": BytesIO(b"not-an-image")},
                HTTP_HOST="acme.app.com", **self.auth,
            )
            self.assertEqual(response.status_code, 403)
            self.assertIn(refused_by, response.json())
        self.assertEqual(self.counts(), before)
        # An update leaves the counts alone, so the one case that edits
        # rather than creates is checked by value.
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.first_name, name)


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

    def test_an_exempt_path_is_no_escape(self):
        # EXEMPT_PATHS returns before host resolution and the 404, and
        # the embed document among them is a plain Django view with no
        # method restriction -- the one route where the authentication
        # guard does not apply either. The middleware guard therefore
        # runs above the exemption, and this is what says so.
        response = self.client.post(
            "/api/v1/embed/anything",
            {},
            content_type="application/json",
            HTTP_HOST="acme.app.com", **self.auth,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("message", response.json())

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
