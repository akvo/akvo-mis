from io import StringIO

from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from django.db.models import Q, Count

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.models import FormData
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_users.models import SystemUser
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_data.functions import set_answer_data
from utils.custom_helper import CustomPasscode
from rest_framework import status


@override_settings(USE_TZ=False, TEST_ENV=True)
class FakeCompleteDataSeederTestCase(TestCase, AssignmentTokenTestHelperMixin):
    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",  # Always use test data
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_form_data_count_equals_repeat_per_form(self):
        repeat = 5
        output = self.call_command("-r", repeat)
        for form in Forms.objects.filter(
            parent__isnull=True
        ).all():
            total_count = FormData.objects.filter(form=form).count()
            self.assertEqual(total_count, repeat)
            expected_msg = (
                f"Created {repeat} data entries for form {form.name}"
            )
            self.assertIn(expected_msg, output)

    def test_monitoring_count_equals_per_form(self):
        repeat = 3
        monitoring = 2
        output = self.call_command("-r", repeat, "-m", monitoring)
        for form in Forms.objects.filter(
            parent__isnull=True,
            children__gt=0,
        ).all():
            total_child_form = form.children.count()
            total_monitoring = form.form_form_data.aggregate(
                total_count=Count('children')
            )['total_count']
            self.assertEqual(
                total_monitoring, repeat * total_child_form * monitoring
            )
            self.assertIn(
                (
                    f"Created {total_monitoring} monitoring data entries "
                    f"for form {form.name}"
                ),
                output
            )

    def test_pending_form_data_half_of_repeat(self):
        repeat = 6
        output = self.call_command(
            "--repeat=%d" % repeat,
            "--approved=false",
        )
        for form in Forms.objects.filter(
            parent__isnull=True
        ).all():
            total_count = form.form_form_data.filter(
                is_pending=True,
                is_draft=False
            ).count()
            self.assertEqual(total_count, repeat // 2)
            expected_msg = (
                f"Created {repeat // 2} pending data entries "
                f"for form {form.name}"
            )
            self.assertIn(expected_msg, output)

    def test_draft_form_data_half_of_repeat(self):
        repeat = 4
        output = self.call_command(
            "--repeat=%d" % repeat,
            "--draft=true",
            "--approved=false",
        )
        for form in Forms.objects.filter(
            parent__isnull=True
        ).all():
            total_count = FormData.objects.filter(
                form=form, is_draft=True
            ).count()
            self.assertEqual(total_count, repeat // 2)
            expected_msg = (
                f"Created {repeat // 2} draft data entries "
                f"for form {form.name}"
            )
            self.assertIn(expected_msg, output)

    def test_each_form_data_has_valid_relationships(self):
        # Create form data with repeat count
        repeat = 2
        self.call_command("-r", repeat)
        form_data_entries = FormData.objects.filter(
            form__children__gt=0,
            is_pending=False,
            is_draft=False
        ).all()
        for form_data in form_data_entries:
            # Each FormData should have a monitoring data (children)
            self.assertTrue(form_data.children.exists())
            for child in form_data.children.all():
                # Each child should have the same UUID as the parent
                self.assertEqual(child.uuid, form_data.uuid)
                if child.submitter:
                    # Each child submitter should have a mobile assignment
                    mobile_assignment_exists = MobileAssignment.objects.filter(
                        user=form_data.created_by,
                        name=child.submitter
                    ).exists()
                    self.assertTrue(mobile_assignment_exists)
            # Each FormData should have a valid user
            # User should have a role with submit access
            # for the administration of the FormData
            self.assertTrue(form_data.created_by.user_user_role.filter(
                Q(
                    role__role_role_access__data_access=DataAccessTypes.submit,
                    administration=form_data.administration
                ) |
                Q(
                    role__role_role_access__data_access=DataAccessTypes.submit,
                    administration__in=[
                        admin for admin in
                        form_data.administration.ancestors.all()
                    ]
                )
            ).exists())

    def test_each_pending_data_should_have_approvers(self):
        # Create form data with repeat count
        repeat = 3
        self.call_command(
            "--repeat=%d" % repeat,
            "--approved=false"
        )
        form_data_entries = FormData.objects.filter(
            is_pending=True,
            is_draft=False
        ).all()
        for form_data in form_data_entries:
            self.assertTrue(form_data.has_approval)
            self.assertTrue(form_data.is_pending)

    def test_each_draft_data_should_not_have_monitoring_data(self):
        # Create form data with repeat count
        repeat = 2
        self.call_command(
            "--repeat=%d" % repeat,
            "--draft=true",
            "--approved=false",
        )
        # Verify each FormData entry
        # Each FormData should have a draft status
        # Each FormData should not have monitoring data
        form_data_entries = FormData.objects.filter(
            is_draft=True
        ).all()
        for form_data in form_data_entries:
            self.assertTrue(form_data.is_draft)
            self.assertFalse(form_data.children.exists())

    def test_each_user_has_valid_role_and_administration(self):
        # Create users with repeat count
        repeat = 2
        self.call_command("--repeat=%d" % repeat, approved=False)
        users = SystemUser.objects.all()
        for user in users:
            for user_role in user.user_user_role.all():
                # Each user role should have a
                # valid administration level and associated role
                self.assertEqual(
                    user_role.role.administration_level,
                    user_role.administration.level
                )

    def test_mobile_user_can_submit_data(self):
        # Create mobile users with repeat count
        repeat = 2
        self.call_command("--repeat=%d" % repeat, approved=False)
        ds = DataAccessTypes.submit
        user = SystemUser.objects.filter(
            user_user_role__role__role_role_access__data_access=ds,
            mobile_assignments__gt=0
        ).order_by('id').first()
        mobile_user = user.mobile_assignments.order_by('id').first()
        self.assertIsNotNone(mobile_user)
        passcode = CustomPasscode().decode(mobile_user.passcode)
        token = self.get_assignment_token(passcode)

        mobile_adm = mobile_user.administrations.first()
        payload = {
            "formId": 1,
            "name": "submit by mobile user",
            "duration": 1,
            "submittedAt": "2025-07-21T02:38:13.807Z",
            "submitter": mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                101: "John Doe",
                102: ["male"],
                103: 62723817,
                104: mobile_adm.id,
                105: [6.2088, 106.8456],
                106: ["wife__husband__partner"],
                107: "photo.jpeg",
                108: "2024-04-29",
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_set_answer_data(self):
        # Use form that have dependency questions
        form = Forms.objects.get(pk=3)
        dep_questions = form.form_questions.filter(
            dependency__isnull=False
        ).distinct()
        dep_values = {}
        for question in dep_questions:
            if question.dependency:
                for d in question.dependency:
                    dep_values[d.get("id")] = d
        q = form.form_questions.filter(
            pk=311
        ).first()

        data = form.form_form_data.order_by('?').first()
        name, value, option = set_answer_data(
            data=data,
            question=q,
            dep_values=dep_values.get(q.id, None)
        )
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsInstance(option, list)

        # Check if dep_values has min value
        dep_values[312] = {
            "id": 312,
            "min": 2
        }
        data = form.form_form_data.order_by('?').first()
        name, value, option = set_answer_data(
            data=data,
            question=q,
            dep_values=dep_values[312]
        )
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsInstance(option, list)

        # Use form that does not have dependency questions
        form = Forms.objects.get(pk=2)
        dep_values = {}
        data = form.form_form_data.order_by('?').first()
        q = form.form_questions.filter(
            pk=203
        ).first()
        name, value, option = set_answer_data(
            data=data,
            question=q,
            dep_values=dep_values.get(q.id, None)
        )
        self.assertIsNone(name)
        self.assertIsInstance(value, int)
        self.assertIsNone(option)
