from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class SubmissionKeyTestCase(TestCase, ProfileTestHelperMixin):
    """The FormData.submission_key constraint, and the webform that uses it.

    The mobile endpoint is covered by
    api.v1.v1_mobile.tests.tests_api_sync_idempotency. Both reach the same
    guard in SubmitPendingFormSerializer.create().
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.form = Forms.objects.get(pk=1)
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.user = self.create_user(
            email="submission.key@test.com",
            role_level=self.IS_SUPER_ADMIN,
            administration=self.administration,
        )
        self.token = RefreshToken.for_user(self.user).access_token

    def create_form_data(self, name, **overrides):
        return FormData.objects.create(
            name=name,
            form=self.form,
            administration=self.administration,
            created_by=self.user,
            **overrides,
        )

    def post_webform(self, **data_overrides):
        adm = Administration.objects.filter(level__level=1).first()
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
                **data_overrides,
            },
            "answer": [
                {"question": 101, "value": "Jane"},
                {"question": 102, "value": ["Male"]},
                {"question": 103, "value": 31208200175},
                {"question": 104, "value": 2.0},
                {"question": 105, "value": [6.2088, 106.8456]},
                {"question": 106, "value": ["Parent", "Children"]},
                {"question": 109, "value": 0},
            ],
        }
        return self.client.post(
            f"/api/v1/form-pending-data/{self.form.id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )

    def test_submission_key_defaults_to_none(self):
        row = self.create_form_data("no key")

        self.assertIsNone(row.submission_key)

    def test_multiple_rows_may_hold_null_submission_key(self):
        # Postgres treats NULLs as distinct under UNIQUE. Tightening this to
        # NOT NULL, or adding a partial index, breaks every keyless caller.
        self.create_form_data("first")
        self.create_form_data("second")
        self.create_form_data("third")

        self.assertEqual(
            FormData.objects.filter(submission_key__isnull=True).count(), 3
        )

    def test_duplicate_submission_key_raises_integrity_error(self):
        key = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        self.create_form_data("first", submission_key=key)

        # The constraint is the real guard, not the application lookup. The
        # atomic() block keeps the IntegrityError from poisoning the test's
        # outer transaction.
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_form_data("second", submission_key=key)

    def test_webform_replay_stores_one_row(self):
        key = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

        first = self.post_webform(submission_key=key)
        second = self.post_webform(submission_key=key)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"message": "ok"})
        self.assertEqual(FormData.objects.filter(form=self.form).count(), 1)

    def test_webform_without_key_creates_two_rows(self):
        # A cached bundle that predates the key must behave exactly as before.
        self.post_webform()
        self.post_webform()

        self.assertEqual(FormData.objects.filter(form=self.form).count(), 2)
