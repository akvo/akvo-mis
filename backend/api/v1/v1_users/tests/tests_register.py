from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

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

    def registered_tenants(self):
        # The backfill data migration seeds a "default" tenant, so it is
        # present in every test database. These tests care only about the
        # tenants registration itself creates.
        return Tenant.objects.exclude(subdomain="default")

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
        self.assertEqual(root.tenant.subdomain, "acme")
        self.assertEqual(Levels.objects.get(level=0).tenant.subdomain, "acme")
        # The control center is only usable if the profile resolves a
        # real administration for the fresh superuser.
        profile = self.client.get(
            "/api/v1/profile",
            HTTP_AUTHORIZATION=f"Bearer {body['token']}",
        )
        self.assertEqual(profile.status_code, 200)
        self.assertIsNotNone(profile.json()["administration"]["id"])

    def test_second_registration_creates_its_own_hierarchy(self):
        self.register()
        response = self.register(email="owner@beta.org", subdomain="beta")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.registered_tenants().count(), 2)
        # Per-tenant hierarchy: each tenant owns a level 0 and a root.
        self.assertEqual(Levels.objects.filter(level=0).count(), 2)
        roots = Administration.objects.filter(parent__isnull=True)
        self.assertEqual(roots.count(), 2)
        self.assertEqual(
            set(roots.values_list("tenant__subdomain", flat=True)),
            {"acme", "beta"},
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
        self.assertEqual(self.registered_tenants().count(), 1)

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
        self.assertEqual(self.registered_tenants().count(), 0)

    def test_weak_password_is_rejected(self):
        response = self.register(password="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.registered_tenants().count(), 0)

    def test_registration_works_on_a_seeded_database(self):
        # administration_seeder inserts levels with explicit ids, which
        # leaves the id sequence behind. Registration now always creates
        # a level of its own, so a desynced sequence makes the very first
        # sign-up on an existing deployment fail with an integrity error.
        call_command("administration_seeder", "--test")
        response = self.register()
        self.assertEqual(response.status_code, 200)

    def test_each_superadmin_resolves_their_own_root(self):
        first = self.register().json()
        second = self.register(
            email="owner@beta.org", subdomain="beta"
        ).json()
        for token, expected in ((first, "acme"), (second, "beta")):
            profile = self.client.get(
                "/api/v1/profile",
                HTTP_AUTHORIZATION=f"Bearer {token['token']}",
            )
            self.assertEqual(profile.status_code, 200)
            self.assertEqual(
                profile.json()["administration"]["name"], expected
            )

    def test_tenantless_superuser_falls_back_to_unscoped_root(self):
        # Legacy path: seeders and createsuperuser make superusers with
        # no tenant; they must keep resolving a root administration.
        call_command("administration_seeder", "--test")
        user = SystemUser.objects.create_superuser(
            email="legacy-admin@example.org",
            password="Secret#Pass123",
            first_name="Legacy",
            last_name="Admin",
        )
        token = str(RefreshToken.for_user(user).access_token)
        profile = self.client.get(
            "/api/v1/profile",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(profile.status_code, 200)
        self.assertIsNotNone(profile.json()["administration"]["id"])
