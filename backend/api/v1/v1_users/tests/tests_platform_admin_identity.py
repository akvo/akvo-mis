from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from api.v1.v1_users.models import SystemUser


class PlatformAdminIdentityTestCase(TestCase):
    """An operator belongs to no workspace and is not a superadmin.

    The two flags are independent on purpose. `is_superuser` already
    means workspace owner everywhere in this codebase, so conflating
    them would hand an operator workspace powers by accident.
    """

    credentials = {
        "email": "ops@akvo.org",
        "password": "Secret#Pass123",
    }

    def test_flag_defaults_to_false(self):
        user = SystemUser.objects.create(email="someone@acme.org")
        self.assertFalse(user.is_platform_admin)

    def test_command_creates_a_tenant_less_operator(self):
        call_command("createplatformadmin", **self.credentials)
        operator = SystemUser.objects.get(email="ops@akvo.org")
        self.assertTrue(operator.is_platform_admin)
        self.assertIsNone(operator.tenant_id)
        self.assertTrue(operator.is_active)
        # Not a workspace owner. An operator that arrived carrying
        # is_superuser would pass every tenant permission check the
        # moment a tenant was in scope.
        self.assertFalse(operator.is_superuser)

    def test_the_operator_can_authenticate(self):
        call_command("createplatformadmin", **self.credentials)
        operator = SystemUser.objects.get(email="ops@akvo.org")
        self.assertTrue(operator.check_password("Secret#Pass123"))

    def test_refuses_a_duplicate_tenant_less_email(self):
        call_command("createplatformadmin", **self.credentials)
        # unique_email_per_tenant cannot catch this: Postgres treats
        # each NULL tenant as distinct, so the database would happily
        # store a second tenant-less row with the same address.
        with self.assertRaises(CommandError):
            call_command("createplatformadmin", **self.credentials)
