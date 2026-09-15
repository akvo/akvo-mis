from io import StringIO
from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False)
class FormSeederTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        # reset_forms must return every form to version 1. Seed once, then
        # set the version directly. What this test asserts is what
        # reset_forms does to an already-versioned form, not how the seeder
        # arrives at a version — double-seeding produced version 2 only
        # because the seeder used to bump unconditionally, which it no
        # longer does.
        call_command("form_seeder", "--test")
        Forms.objects.update(version=2)

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "reset_forms",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_call_reset_forms_command(self):
        # Show version of the forms before reset
        initial_forms = Forms.objects.all().values_list('id', 'version')
        initial_forms_dict = {form[0]: form[1] for form in initial_forms}
        # Ensure there are forms to reset
        self.assertGreater(len(initial_forms_dict), 0, "No forms to reset.")
        # Check the initial version of the forms
        for form_id, version in initial_forms_dict.items():
            self.assertEqual(
                version,
                2,
                f"Form {form_id} is not at version 2."
            )
        output = self.call_command("--test")
        # Check if the output contains the success message
        self.assertIn("Successfully reset all forms.", output)
        # Check if the forms are reset
        reset_forms = Forms.objects.all().values_list('id', 'version')
        reset_forms_dict = {form[0]: form[1] for form in reset_forms}
        # Ensure forms are still present after reset
        self.assertGreater(len(reset_forms_dict), 0, "No forms after reset.")
        # Check if the forms are reset to version 1
        for form_id, version in reset_forms_dict.items():
            self.assertEqual(
                version,
                1,
                f"Form {form_id} is not reset to version 1."
            )
        # Ensure the reset command does not create new forms
        self.assertEqual(
            len(initial_forms_dict),
            len(reset_forms_dict),
            "Reset command created new forms."
        )
        # Ensure the reset command did not delete any forms
        self.assertEqual(
            set(initial_forms_dict.keys()),
            set(reset_forms_dict.keys()),
            "Reset command deleted some forms."
        )
        # Ensure the reset command did not change the IDs of the forms
        for form_id in initial_forms_dict.keys():
            self.assertIn(
                form_id,
                reset_forms_dict,
                f"Form {form_id} was deleted during reset."
            )

    def test_call_reset_forms_with_users_form_assignment(self):
        call_command("administration_seeder", "--test", 1)
        # Create a user and assign a form to them
        adm = Administration.objects.filter(
            level__level=2
        ).order_by("?").first()
        form = Forms.objects.get(pk=1)
        user = self.create_user(
            email="user@example.com",
            role_level=self.IS_ADMIN,
            administration=adm,
            form=form,
        )
        total_before = user.user_form.count()
        output = self.call_command("--test")
        self.assertIn("Successfully reset all forms.", output)
        user.refresh_from_db()

        total_after = user.user_form.count()

        self.assertEqual(
            total_before,
            total_after,
            "User's form assignments changed after reset."
        )

        # Check if the user has the form assigned after reset
        self.assertIn(
            form,
            [
                uf.form for uf in user.user_form.all()
            ],
            "User does not have the form assigned after reset."
        )
