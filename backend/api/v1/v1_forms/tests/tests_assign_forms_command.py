from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False)
class AssignFormsCommandTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

    def test_command_assign_forms(self):
        # Call the command to assign forms
        output = StringIO()
        user = SystemUser.objects.create(
            email="dev@akvo.org",
            first_name="Test",
            last_name="Superadmin",
            is_superuser=True,
        )
        email = user.email
        call_command(
            "assign_forms",
            email,
            stdout=output,
            stderr=StringIO(),
        )

        # Check if the command executed successfully
        count_forms = Forms.objects.filter(parent__isnull=True).count()
        self.assertIn(
            (
                f"Successfully assigned {count_forms} forms "
                f"to user {user.email}."
            ),
            output.getvalue()
        )

    def test_command_fails_for_missing_user(self):
        with self.assertRaises(CommandError):
            call_command("assign_forms", "missing@example.test")
