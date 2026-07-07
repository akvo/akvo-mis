from django.core.management import call_command
from django.test import TestCase, override_settings
from django.db.models import Count
from api.v1.v1_jobs.functions import ValidationText
from api.v1.v1_jobs.validate_upload import validate
from api.v1.v1_jobs.models import Jobs, JobTypes, JobStatus
from api.v1.v1_jobs.seed_data import seed_excel_data
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_data.models import FormData
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.models import Administration, Role, UserRole
from api.v1.v1_profile.constants import DataAccessTypes
from api.v1.v1_approval.models import DataBatch, DataBatchList
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_data.management.commands.fake_complete_data_seeder import (
    add_fake_answers
)
from api.v1.v1_profile.functions import get_max_administration_level


@override_settings(USE_TZ=False, TEST_ENV=True)
class BulkUploadDataTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

        user_payload = {"email": "admin@akvo.org", "password": "Test105*"}
        user_response = self.client.post('/api/v1/login',
                                         user_payload,
                                         content_type='application/json')
        res = user_response.json()
        self.user = SystemUser.objects.filter(
            email=res["email"]
        ).first()

        self.test_folder = "api/v1/v1_jobs/tests/fixtures"

    def _make_user(self, email, data_access, administration, form):
        """Create a non-superadmin user with a role that has the given data
        access at ``administration`` plus access to ``form``."""
        user = SystemUser.objects.create(
            email=email,
            first_name=email.split("@")[0],
            last_name="Test",
            is_superuser=False,
        )
        user.set_password("test")
        user.save()
        role = Role.objects.filter(
            role_role_access__data_access=data_access
        ).first()
        UserRole.objects.create(
            user=user, role=role, administration=administration
        )
        UserForms.objects.get_or_create(user=user, form=form)
        return user

    def _seed_as(self, user, form, administration, upload_file):
        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=user,
            info={
                "file": upload_file,
                "form": form.id,
                "administration": administration.id,
                "is_update": False,
            },
        )
        return seed_excel_data(job=job, test=True)

    def test_non_super_bulk_upload_seeds_all_rows_with_answers(self):
        """Regression: a non-superadmin bulk upload must turn EVERY row into a
        pending datapoint WITH answers, linked to a batch.

        Previously ``seed_excel_data`` called
        ``batch.batch_data_list.add(data)`` which raised ``TypeError``
        (``DataBatchList`` is a through model, not an m2m to ``FormData``),
        aborting the seed after the first datapoint — leaving a single
        answerless datapoint behind.
        """
        call_command("default_roles_seeder", "--test", 1)
        form = Forms.objects.get(pk=1)
        administration = Administration.objects.filter(name="Cawang").first()
        submitter = self._make_user(
            "bulk.submitter@test.com",
            DataAccessTypes.submit,
            administration,
            form,
        )
        upload_file = "{0}/test-success-new-registration.xlsx".format(
            self.test_folder
        )
        self.assertEqual(
            len(
                validate(
                    form=form,
                    administration=administration.id,
                    file=upload_file,
                )
            ),
            0,
        )
        records = self._seed_as(submitter, form, administration, upload_file)

        datapoints = FormData.objects.filter(
            form=form, created_by=submitter, is_pending=True
        )
        # Fixture has 2 rows: both must be seeded (not just the first).
        self.assertEqual(datapoints.count(), 2)
        self.assertEqual(len(records), 2)
        for dp in datapoints:
            self.assertGreater(
                dp.data_answer.count(),
                0,
                "pending datapoint must have answers",
            )
            self.assertTrue(
                DataBatchList.objects.filter(data=dp).exists(),
                "datapoint must be linked to a batch",
            )

    def test_non_super_bulk_upload_notifies_approvers(self):
        """The approver-notification path must resolve emails from
        ``batch.approvers()`` (which returns dicts, not model instances).

        Previously it did ``approver.user.email`` and raised
        ``AttributeError: 'dict' object has no attribute 'user'``.
        """
        call_command("default_roles_seeder", "--test", 1)
        form = Forms.objects.get(pk=1)
        administration = Administration.objects.filter(name="Cawang").first()
        submitter = self._make_user(
            "bulk.submitter2@test.com",
            DataAccessTypes.submit,
            administration,
            form,
        )
        approver = self._make_user(
            "bulk.approver@test.com",
            DataAccessTypes.approve,
            administration,
            form,
        )
        upload_file = "{0}/test-success-new-registration.xlsx".format(
            self.test_folder
        )
        records = self._seed_as(submitter, form, administration, upload_file)
        self.assertTrue(records)

        batch = DataBatch.objects.filter(user=submitter).last()
        self.assertIsNotNone(batch)
        approver_emails = [a["user"].email for a in batch.approvers()]
        self.assertIn(approver.email, approver_emails)

        # DataApproval rows must be created so the batch is approvable and its
        # approvers show up in the /batch/ list (batch_approval relation).
        self.assertTrue(
            batch.batch_approval.filter(user=approver).exists(),
            "a DataApproval must be assigned to the approver",
        )

    def test_bulk_uploaded_batch_lists_approvers_via_endpoint(self):
        """End-to-end: the /batch/ list endpoint must show the approvers of a
        bulk-uploaded batch.

        The endpoint's serializer reads ``batch_approval`` (DataApproval rows),
        not ``batch.approvers()``. Bulk-uploaded batches previously had no
        DataApproval rows, so the ``approvers`` field came back empty.
        """
        call_command("default_roles_seeder", "--test", 1)
        form = Forms.objects.get(pk=1)
        administration = Administration.objects.filter(name="Cawang").first()
        submitter = self._make_user(
            "bulk.submitter3@test.com",
            DataAccessTypes.submit,
            administration,
            form,
        )
        approver = self._make_user(
            "bulk.approver2@test.com",
            DataAccessTypes.approve,
            administration,
            form,
        )
        upload_file = "{0}/test-success-new-registration.xlsx".format(
            self.test_folder
        )
        self._seed_as(submitter, form, administration, upload_file)

        token = self.get_auth_token(submitter.email, "test")
        response = self.client.get(
            f"/api/v1/batch/?form={form.id}&page=1",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(len(body["data"]), 1)
        batch_json = body["data"][0]
        approver_names = [a["name"] for a in batch_json["approvers"]]
        self.assertIn(approver.get_full_name(), approver_names)

    def test_upload_empty_data(self):
        form = Forms.objects.get(pk=1)
        MAX_ADM_LEVEL = get_max_administration_level()
        administration = Administration.objects.filter(
            level__level=MAX_ADM_LEVEL
        ).first()
        upload_file = f"{self.test_folder}/test-error-empty-data.xlsx"
        output = validate(
            form=form,
            administration=administration.id,
            file=upload_file
        )
        self.assertEqual(
            output[0]["error_message"],
            ValidationText.file_empty_validation.value
        )

    def test_upload_error_dependency(self):
        form = Forms.objects.get(pk=1)
        upload_file = "{0}/test-error-dependency.xlsx".format(
            self.test_folder
        )

        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        output = validate(
            form=form,
            administration=administration.id,
            file=upload_file
        )
        self.assertEqual(len(output), 2)
        self.assertEqual(
            output[0]["error_message"],
            "whats_the_pet {0}".format(
                ValidationText.should_be_empty.value
            )
        )
        self.assertEqual(
            output[1]["error_message"],
            "whats_the_pet {0}".format(
                ValidationText.is_required.value
            )
        )

    def test_upload_new_registration_data(self):
        form = Forms.objects.get(pk=1)
        upload_file = "{0}/test-success-new-registration.xlsx".format(
            self.test_folder
        )

        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        validation = validate(
            form=form,
            administration=administration.id,
            file=upload_file
        )
        self.assertEqual(len(validation), 0)

        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=self.user,
            info={
                "file": upload_file,
                "form": form.id,
                "is_update": False,
            },
        )
        seed_excel_data(job=job, test=True)

        name1 = "John Doe - 23911 - Cawang - wife__husband__partner"
        dp1 = form.form_form_data.filter(
            name=name1
        ).first()
        self.assertTrue(dp1)

        name2 = "Jane Doe - 1123912 - Cawang - parent"
        dp2 = form.form_form_data.filter(
            name=name2
        ).first()
        self.assertTrue(dp2)

    def test_upload_update_registration_data(self):
        form = Forms.objects.get(pk=1)
        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        name = "new - John Doe - 44 – wife__husband__partner"
        FormData.objects.all().delete()
        data = FormData.objects.create(
            id=1,
            name=name,
            geo=["-8.6384108", "116.2469499"],
            form=form,
            administration=administration,
            created_by=self.user,
        )
        data.save()
        add_fake_answers(data)

        upload_file = "{0}/test-success-update-registration.xlsx".format(
            self.test_folder
        )
        validation = validate(
            form=form,
            administration=administration.id,
            file=upload_file
        )

        self.assertEqual(len(validation), 0)

        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=self.user,
            info={
                "file": upload_file,
                "form": form.id,
                "is_update": False,
            },
        )
        seed_excel_data(job=job, test=True)

        updated_dp = FormData.objects.annotate(
            history_count=Count("data_answer_history")
        ).filter(
            form=form,
            history_count__gt=0
        ).first()
        self.assertTrue(updated_dp)

    def test_upload_new_monitoring_data(self):
        form = Forms.objects.get(pk=1)
        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        FormData.objects.all().delete()
        name = "new - Jane Doe - 44 – wife__husband__partner"
        data = FormData.objects.create(
            id=9999,
            name=name,
            geo=["-8.6384108", "116.2469499"],
            form=form,
            administration=administration,
            created_by=self.user,
        )
        data.save()
        add_fake_answers(data)

        upload_file = "{0}/test-success-new-monitoring.xlsx".format(
            self.test_folder
        )

        datapoint = form.form_form_data.first()
        datapoint.save()

        validation = validate(
            form=form,
            administration=datapoint.administration.id,
            file=upload_file
        )
        self.assertEqual(len(validation), 0)

        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=self.user,
            info={
                "file": upload_file,
                "form": form.id,
                "is_update": False,
            },
        )
        seed_excel_data(job=job, test=True)
        # TODO: Update assert to check monitoring data
        # data_count = FormData.objects.filter(
        #     uuid=datapoint.uuid
        # ).count()

        # self.assertGreater(data_count, 1)

    def test_upload_error_multi_dependency(self):
        form3 = Forms.objects.get(pk=3)
        upload_file = "{0}/test-error-multi-dependency.xlsx".format(
            self.test_folder
        )

        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        output = validate(
            form=form3,
            administration=administration.id,
            file=upload_file
        )

        self.assertEqual(len(output), 1)
        self.assertEqual(
            output[0]["error_message"],
            "which_days_classrooms_cleaned {0}".format(
                ValidationText.should_be_empty.value
            )
        )

    def test_upload_success_multi_dependency(self):
        form3 = Forms.objects.get(pk=3)
        upload_file = "{0}/test-success-multi-dependency.xlsx".format(
            self.test_folder
        )

        administration = Administration.objects.filter(
            name="Cawang"
        ).first()
        validation = validate(
            form=form3,
            administration=administration.id,
            file=upload_file
        )

        self.assertEqual(len(validation), 0)

        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=self.user,
            info={
                "file": upload_file,
                "form": form3.id,
                "is_update": False,
            },
        )
        seed_excel_data(job=job, test=True)
        name1 = "SD Cawang 1"
        dp1 = form3.form_form_data.filter(
            name=name1
        ).first()
        self.assertTrue(dp1)

        all = form3.form_form_data.count()
        self.assertEqual(all, 2)
