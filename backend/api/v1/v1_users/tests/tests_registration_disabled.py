from django.test import TestCase, override_settings

from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(ALLOW_REGISTRATION=False)
class RegistrationDisabledTestCase(TestCase):
    """A dedicated single-customer deployment has nobody to sign up.

    The flag defaults on — the SaaS deployment and the inherited
    registration tests both need that — so this suite is the only place
    the off state is exercised.
    """

    payload = {
        "email": "founder@acme.org",
        "password": "Secret#Pass123",
        "subdomain": "acme",
    }

    def register(self):
        return self.client.post(
            "/api/v1/register",
            self.payload,
            content_type="application/json",
        )

    def test_registration_is_refused(self):
        self.assertEqual(self.register().status_code, 403)

    def test_no_tenant_or_user_is_created(self):
        self.register()
        # The backfill migration seeds "default" in every test database.
        self.assertFalse(
            Tenant.objects.exclude(subdomain="default").exists()
        )
        self.assertFalse(
            SystemUser.objects.filter(email=self.payload["email"]).exists()
        )
