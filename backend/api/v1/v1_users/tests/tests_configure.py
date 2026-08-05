from unittest import mock

from django.core import signing
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False)
class ConfigureProjectTestCase(TestCase):
    """Phase 2: the workspace names itself and gains its hierarchy root.

    This is the first point at which we know the email is real, which is
    why the registrant's own name is collected here rather than at sign-up.
    """

    config = {
        "first_name": "Ada",
        "last_name": "Founder",
        "level_0_name": "National",
        "root_unit_name": "Kenya",
    }

    def signup(self, email="founder@acme.org", subdomain="acme"):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.client.post(
                "/api/v1/register",
                {"email": email, "password": "Secret#Pass123",
                 "subdomain": subdomain},
                content_type="application/json",
            )
        user = SystemUser.objects.get(email=email)
        token = self.client.post(
            "/api/v1/register/activate",
            {"token": signing.dumps(user.pk)},
            content_type="application/json",
        ).json()["token"]
        return user, {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def configure(self, auth, **overrides):
        return self.client.post(
            "/api/v1/register/configure", {**self.config, **overrides},
            content_type="application/json", **auth
        )

    def test_activated_user_starts_unconfigured(self):
        _, auth = self.signup()
        res = self.client.get("/api/v1/profile", **auth)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["configured"])

    def test_configure_names_the_user_and_builds_the_root(self):
        user, auth = self.signup()
        res = self.configure(auth)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["configured"])

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Founder")

        level = Levels.objects.get(tenant=user.tenant, level=0)
        self.assertEqual(level.name, "National")
        root = Administration.objects.get(
            tenant=user.tenant, parent__isnull=True
        )
        # Named as entered, not after the subdomain — this is what removes
        # the placeholder root the bulk-upload template had to reconcile.
        self.assertEqual(root.name, "Kenya")
        self.assertEqual(root.level, level)

    def test_the_profile_resolves_an_administration_once_configured(self):
        _, auth = self.signup()
        self.configure(auth)
        res = self.client.get("/api/v1/profile", **auth)
        self.assertEqual(res.json()["administration"]["name"], "Kenya")

    def test_configuring_twice_is_rejected(self):
        _, auth = self.signup()
        self.configure(auth)
        res = self.configure(auth, root_unit_name="Uganda")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            Administration.objects.filter(name="Uganda").count(), 0
        )

    def test_configure_requires_authentication(self):
        res = self.client.post(
            "/api/v1/register/configure", self.config,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_missing_fields_are_rejected_and_create_nothing(self):
        user, auth = self.signup()
        res = self.configure(auth, level_0_name="")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Levels.objects.filter(tenant=user.tenant).exists())

    def test_tenants_configure_independently(self):
        acme_user, acme = self.signup()
        beta_user, beta = self.signup(
            email="owner@beta.org", subdomain="beta"
        )
        self.configure(acme)
        # Configuring one workspace must not mark the other configured.
        self.assertTrue(
            self.client.get("/api/v1/profile", **acme).json()["configured"]
        )
        self.assertFalse(
            self.client.get("/api/v1/profile", **beta).json()["configured"]
        )
        self.assertFalse(
            Levels.objects.filter(tenant=beta_user.tenant).exists()
        )

    def test_configure_works_on_a_seeded_database(self):
        # administration_seeder inserts levels with explicit ids, which
        # leaves the id sequence behind. Creating level 0 has moved from
        # register to here, so this is where a desynced sequence would make
        # the first sign-up on an existing deployment fail.
        call_command("administration_seeder", "--test")
        _, auth = self.signup()
        self.assertEqual(self.configure(auth).status_code, 200)
