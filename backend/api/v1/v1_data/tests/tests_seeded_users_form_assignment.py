"""Every seeded account gets the monitoring form, not just the root.

`UserSerializer.get_forms` returns `user_form.all()` verbatim, and the
mobile assignment screen reads monitoring forms out of that same list as
the children of each registration form. Three writers created UserForms
rows and all three assigned roots only -- `assign_forms` for the
superadmin, and the approver and submitter branches of
fake_complete_data_seeder -- so no seeded account in any workspace could
attach a monitoring form to a device.
"""
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class SeededUsersGetMonitoringFormsTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command(
            "fake_complete_data_seeder",
            "--test", True,
            "--repeat", 2,
            "--monitoring", 1,
            "--approved", "false",
        )

    def seeded_users(self):
        return SystemUser.objects.filter(email__contains="@test.com")

    def test_the_seeder_created_accounts(self):
        self.assertTrue(self.seeded_users().exists())

    def test_every_seeded_account_has_a_monitoring_form(self):
        """The defect, stated as the property it broke."""
        # parent__isnull=False, not just type=monitoring: example-2.json
        # is a monitoring form with no parent, so it passed the old
        # roots-only filter and a type-only assertion proved nothing.
        # What the assignment tree needs is the forms that HAVE a parent.
        children = set(
            Forms.objects.filter(parent__isnull=False).values_list(
                "id", flat=True
            )
        )
        self.assertTrue(children, "fixture has no child forms")
        without = []
        for user in self.seeded_users():
            assigned = set(
                UserForms.objects.filter(user=user).values_list(
                    "form_id", flat=True
                )
            )
            if not children <= assigned:
                without.append(user.email)
        self.assertEqual(
            without, [], "seeded accounts missing child form assignments"
        )

    def test_every_seeded_account_still_has_a_registration_form(self):
        for user in self.seeded_users():
            self.assertTrue(
                UserForms.objects.filter(
                    user=user, form__type=FormTypes.registration
                ).exists(),
                f"{user.email} lost its registration form",
            )

    def test_every_assigned_child_has_its_parent_assigned(self):
        """A child whose parent is unassigned cannot be reached in the
        assignment tree, which nests monitoring forms under their
        registration form."""
        for user in self.seeded_users():
            assigned = set(
                UserForms.objects.filter(user=user).values_list(
                    "form_id", flat=True
                )
            )
            for child in Forms.objects.filter(
                id__in=assigned, parent__isnull=False
            ):
                self.assertIn(child.parent_id, assigned)

    def test_no_duplicate_assignments(self):
        for user in self.seeded_users():
            rows = list(
                UserForms.objects.filter(user=user).values_list(
                    "form_id", flat=True
                )
            )
            self.assertEqual(len(rows), len(set(rows)))

    def test_only_published_forms_are_assigned(self):
        assigned = Forms.objects.filter(
            form_user__user__in=self.seeded_users()
        ).distinct()
        for form in assigned:
            self.assertEqual(form.status, FormStatus.published)
