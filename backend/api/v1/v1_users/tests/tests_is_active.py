from django.contrib.auth import authenticate
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False)
class IsActiveTestCase(TestCase):
    """`is_active` as a real column rather than an inherited constant.

    AbstractBaseUser defines `is_active = True` as a class attribute, so
    every check in Django and simplejwt was already running and always
    passing. These assertions pin that the field now actually gates both
    password auth and token auth.
    """

    def _create(self, email, **extra):
        return SystemUser.objects.create_user(
            email=email, password="Secret#Pass123",
            first_name="A", last_name="A", **extra
        )

    def test_new_users_active_by_default(self):
        # Seeders, createsuperuser, invited users and every existing row
        # depend on this default.
        self.assertTrue(self._create("a@example.org").is_active)

    def test_inactive_user_cannot_authenticate(self):
        self._create("b@example.org", is_active=False)
        self.assertIsNone(
            authenticate(email="b@example.org", password="Secret#Pass123")
        )

    def test_active_user_authenticates(self):
        self._create("c@example.org")
        self.assertIsNotNone(
            authenticate(email="c@example.org", password="Secret#Pass123")
        )

    def test_inactive_user_token_is_refused(self):
        # A token minted before deactivation must stop working: simplejwt's
        # get_user raises on an inactive user, which is what stops an
        # unverified registrant using the token any endpoint handed them.
        user = self._create("d@example.org", is_active=False)
        token = RefreshToken.for_user(user).access_token
        res = self.client.get(
            "/api/v1/profile", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(res.status_code, 401)
