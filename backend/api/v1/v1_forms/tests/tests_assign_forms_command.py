from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class AssignFormsCommandTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

    def make_user(self, email="dev@akvo.org", tenant=None):
        return SystemUser.objects.create(
            email=email,
            first_name="Test",
            last_name="Superadmin",
            is_superuser=True,
            tenant=tenant,
        )

    def published(self, tenant=None):
        return Forms.objects.filter(
            status=FormStatus.published, tenant=tenant
        )

    def test_command_assign_forms(self):
        output = StringIO()
        user = self.make_user()

        call_command(
            "assign_forms", user.email, stdout=output, stderr=StringIO()
        )

        count_forms = self.published().count()
        self.assertIn(
            (
                f"Successfully assigned {count_forms} forms "
                f"to user {user.email}."
            ),
            output.getvalue(),
        )

    def test_monitoring_forms_are_assigned_too(self):
        """The mobile assignment screen builds its tree from these rows.

        `UserSerializer.get_forms` returns `user_form.all()` verbatim, and
        AddAssignment.jsx reads monitoring forms out of that same list as
        the children of each registration form. Assigning only roots --
        `parent__isnull=True`, which this command used to do -- left every
        registration form with no children to offer, so a device could
        never be given a monitoring form.
        """
        user = self.make_user()

        call_command(
            "assign_forms", user.email, stdout=StringIO(), stderr=StringIO()
        )

        assigned = Forms.objects.filter(form_user__user=user)
        # parent__isnull=False, not just type=monitoring: example-2.json
        # is a monitoring form with no parent, so it passed the old
        # roots-only filter and made a type-only assertion vacuous. The
        # tree's children are the ones that HAVE a parent.
        children = Forms.objects.filter(parent__isnull=False)
        self.assertTrue(children.exists(), "fixture has no child forms")
        self.assertEqual(
            set(children.values_list("id", flat=True))
            - set(assigned.values_list("id", flat=True)),
            set(),
            "child forms were left unassigned",
        )
        self.assertTrue(assigned.filter(type=FormTypes.registration).exists())

    def test_every_assigned_monitoring_form_has_its_parent_assigned(self):
        """A child with no assigned parent cannot be reached in the tree."""
        user = self.make_user()

        call_command(
            "assign_forms", user.email, stdout=StringIO(), stderr=StringIO()
        )

        assigned_ids = set(
            UserForms.objects.filter(user=user).values_list(
                "form_id", flat=True
            )
        )
        children = Forms.objects.filter(
            id__in=assigned_ids, parent__isnull=False
        )
        for child in children:
            self.assertIn(child.parent_id, assigned_ids)

    def test_a_draft_form_is_not_assigned(self):
        draft = Forms.objects.create(
            name="Draft form", version=1, status=FormStatus.draft
        )
        user = self.make_user()

        call_command(
            "assign_forms", user.email, stdout=StringIO(), stderr=StringIO()
        )

        self.assertFalse(
            UserForms.objects.filter(user=user, form=draft).exists()
        )

    def test_rerunning_assigns_nothing_new_and_duplicates_nothing(self):
        user = self.make_user()
        call_command(
            "assign_forms", user.email, stdout=StringIO(), stderr=StringIO()
        )
        before = UserForms.objects.filter(user=user).count()

        output = StringIO()
        call_command(
            "assign_forms", user.email, stdout=output, stderr=StringIO()
        )

        self.assertEqual(UserForms.objects.filter(user=user).count(), before)
        self.assertIn("Successfully assigned 0 forms", output.getvalue())

    def test_only_the_users_own_workspace_forms_are_assigned(self):
        other = Tenant.objects.create(subdomain="other")
        theirs = Forms.objects.create(
            name="Their form",
            version=1,
            status=FormStatus.published,
            tenant=other,
        )
        user = self.make_user()

        call_command(
            "assign_forms", user.email, stdout=StringIO(), stderr=StringIO()
        )

        self.assertFalse(
            UserForms.objects.filter(user=user, form=theirs).exists()
        )

    def test_command_fails_for_missing_user(self):
        with self.assertRaises(CommandError):
            call_command("assign_forms", "missing@example.test")
