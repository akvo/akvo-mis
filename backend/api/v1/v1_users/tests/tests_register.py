from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class RegisterEndpointTestCase(TestCase):
    payload = {
        "email": "founder@acme.org",
        "password": "Secret#Pass123",
        "first_name": "Ada",
        "last_name": "Founder",
        "subdomain": "acme",
    }

    def register(self, **overrides):
        payload = {**self.payload, **overrides}
        return self.client.post(
            "/api/v1/register", payload, content_type="application/json"
        )

    def test_register_on_empty_database_bootstraps_everything(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("token", body)
        user = SystemUser.objects.get(email="founder@acme.org")
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.tenant.subdomain, "acme")
        self.assertTrue(Levels.objects.filter(level=0).exists())
        root = Administration.objects.get(parent__isnull=True)
        self.assertEqual(root.name, "acme")
        # The control center is only usable if the profile resolves a
        # real administration for the fresh superuser.
        profile = self.client.get(
            "/api/v1/profile",
            HTTP_AUTHORIZATION=f"Bearer {body['token']}",
        )
        self.assertEqual(profile.status_code, 200)
        self.assertIsNotNone(profile.json()["administration"]["id"])

    def test_second_registration_reuses_the_hierarchy(self):
        self.register()
        response = self.register(email="owner@beta.org", subdomain="beta")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Tenant.objects.count(), 2)
        self.assertEqual(Levels.objects.filter(level=0).count(), 1)
        self.assertEqual(
            Administration.objects.filter(parent__isnull=True).count(), 1
        )

    def test_duplicate_subdomain_is_rejected_atomically(self):
        self.register()
        response = self.register(email="owner@beta.org")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "Subdomain is already registered"
        )
        self.assertFalse(
            SystemUser.objects.filter(email="owner@beta.org").exists()
        )

    def test_duplicate_email_is_rejected(self):
        self.register()
        response = self.register(subdomain="beta")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "Email is already registered"
        )
        self.assertEqual(Tenant.objects.count(), 1)

    def test_losing_a_uniqueness_race_is_a_400(self):
        # Two simultaneous sign-ups can both pass the serializer's
        # existence checks; the loser hits the unique constraint at
        # insert. Stand in for that with a raising create.
        with mock.patch(
            "api.v1.v1_users.views.Tenant.objects.create",
            side_effect=IntegrityError("duplicate key"),
        ):
            response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SystemUser.objects.count(), 0)

    def test_malformed_subdomain_is_rejected(self):
        for bad in ("My App", "UPPER", "-lead", "trail-", "a_b"):
            response = self.register(subdomain=bad)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Tenant.objects.count(), 0)

    def test_weak_password_is_rejected(self):
        response = self.register(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Tenant.objects.count(), 0)
