from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class MobileSyncIdempotencyTest(
    TestCase, AssignmentTokenTestHelperMixin, ProfileTestHelperMixin
):
    """POST /device/sync must store a replayed submission exactly once.

    A submission is replayed whenever the device sent it, the backend
    committed it, and the acknowledgement never arrived -- a killed process,
    a timeout, a proxy 502. The device then finds syncedAt still NULL and
    sends again.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        adm_level = Levels.objects.filter(level__gt=0).order_by("?").first()
        self.administration = Administration.objects.filter(
            level=adm_level
        ).order_by("?").last()

        self.form = Forms.objects.filter(parent__isnull=True).first()
        self.monitoring_form = Forms.objects.filter(
            parent__isnull=False
        ).first()

        self.user = self.create_user(
            email="test@test.org",
            administration=self.administration,
            role_level=self.IS_ADMIN,
            form=self.form,
        )
        self.passcode = "passcode1234"
        MobileAssignment.objects.create_assignment(
            user=self.user, name="test assignment", passcode=self.passcode
        )
        self.mobile_assignment = MobileAssignment.objects.get(user=self.user)
        self.mobile_assignment.administrations.add(
            *Administration.objects.filter(parent=self.administration).all()
        )
        self.mobile_assignment.forms.add(self.form)
        self.token = self.get_assignment_token(self.passcode)

    def build_answers(self, form):
        response = self.client.get(
            f"/api/v1/device/form/{form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        answers = {}
        for question_group in response.json()["question_group"]:
            for q in question_group["question"]:
                if q["type"] in ("option", "multiple_option"):
                    answers[q["id"]] = [q["option"][0]["value"]]
                elif q["type"] == "number":
                    answers[q["id"]] = 12
                elif q["type"] == "geo":
                    answers[q["id"]] = [0, 0]
                elif q["type"] == "date":
                    answers[q["id"]] = "2021-01-01T00:00:00.000Z"
                elif q["type"] == "image":
                    answers[q["id"]] = "https://picsum.photos/200/300"
                elif q["type"] in ("cascade", "administration"):
                    answers[q["id"]] = self.administration.id
                else:
                    answers[q["id"]] = "testing"
        return answers

    def post_sync(self, form=None, query="", **overrides):
        form = form or self.form
        payload = {
            "formId": form.id,
            "name": "testing datapoint",
            "duration": 3000,
            "submittedAt": "2021-01-01T00:00:00.000Z",
            "geo": [0, 0],
            "answers": self.build_answers(form),
        }
        payload.update(overrides)
        return self.client.post(
            f"/api/v1/device/sync{query}",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )

    def test_replayed_submission_key_stores_one_row(self):
        key = "11111111-1111-1111-1111-111111111111"

        first = self.post_sync(submission_key=key)
        second = self.post_sync(submission_key=key)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        # The row count is the assertion. A broken build returns 200 twice.
        self.assertEqual(FormData.objects.filter(form=self.form).count(), 1)

    def test_replay_does_not_duplicate_answers(self):
        key = "22222222-2222-2222-2222-222222222222"

        self.post_sync(submission_key=key)
        row = FormData.objects.filter(form=self.form).first()
        answers_after_first = Answers.objects.filter(data=row).count()

        self.post_sync(submission_key=key)

        # A guard placed after serializer.save() would dedupe the FormData row
        # and still write every answer a second time.
        self.assertEqual(
            Answers.objects.filter(data=row).count(), answers_after_first
        )

    def test_omitted_submission_key_creates_two_rows(self):
        self.post_sync()
        self.post_sync()

        self.assertEqual(FormData.objects.filter(form=self.form).count(), 2)

    def test_distinct_keys_create_distinct_rows(self):
        parent = FormData.objects.create(
            name="parent datapoint",
            form=self.form,
            administration=self.administration,
            created_by=self.user,
        )

        first = self.post_sync(
            form=self.monitoring_form,
            uuid=str(parent.uuid),
            submission_key="33333333-3333-3333-3333-333333333333",
        )
        second = self.post_sync(
            form=self.monitoring_form,
            uuid=str(parent.uuid),
            submission_key="44444444-4444-4444-4444-444444444444",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        # Two monitoring visits to one household share a uuid and are both
        # legitimate. This fails if anyone reverts the key to uuid.
        children = FormData.objects.filter(form=self.monitoring_form)
        self.assertEqual(children.count(), 2)
        self.assertEqual(children.filter(parent=parent).count(), 2)

    def test_replay_returns_original_row_id(self):
        key = "88888888-8888-8888-8888-888888888888"

        first = self.post_sync(submission_key=key)
        second = self.post_sync(submission_key=key)

        row = FormData.objects.filter(form=self.form).first()
        self.assertEqual(first.json()["id"], row.id)
        # The replay early-return must expose the original row's identity,
        # not mint a new one.
        self.assertEqual(second.json()["id"], row.id)

    def test_monitoring_draft_resave_with_returned_id_updates_in_place(self):
        parent = FormData.objects.create(
            name="parent datapoint",
            form=self.form,
            administration=self.administration,
            created_by=self.user,
        )

        # First save of a monitoring draft: the device has no draftId yet.
        first = self.post_sync(
            form=self.monitoring_form,
            query="?is_draft=true",
            uuid=str(parent.uuid),
            submission_key="99999999-9999-9999-9999-999999999999",
        )
        draft_id = first.json()["id"]

        # The uuid fallback cannot match child forms (a monitoring draft
        # carries its PARENT's uuid), so the returned id is the only thing
        # standing between a re-saved draft and a duplicate row. The device
        # stores it as draftId and re-saves with ?id=.
        second = self.post_sync(
            form=self.monitoring_form,
            query=f"?is_draft=true&id={draft_id}",
            uuid=str(parent.uuid),
            submission_key="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )

        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json()["id"], draft_id)
        self.assertEqual(
            FormData.objects_draft.filter(
                form=self.monitoring_form
            ).count(),
            1,
        )

    def test_draft_resave_still_updates_in_place(self):
        self.post_sync(
            query="?is_draft=true",
            uuid="55555555-5555-5555-5555-555555555555",
            submission_key="66666666-6666-6666-6666-666666666666",
        )
        # A draft save mints a fresh key each time; draft_exists matches on
        # uuid and updates in place. The two mechanisms must not collide.
        self.post_sync(
            query="?is_draft=true",
            uuid="55555555-5555-5555-5555-555555555555",
            submission_key="77777777-7777-7777-7777-777777777777",
        )

        self.assertEqual(
            FormData.objects_draft.filter(form=self.form).count(), 1
        )

    def test_replay_of_published_submission_is_noop(self):
        key = "88888888-8888-8888-8888-888888888888"

        self.post_sync(submission_key=key)
        row = FormData.objects.filter(form=self.form).first()

        # draft_exists cannot catch this: the row is published, not a draft.
        self.post_sync(query="?is_published=true", submission_key=key)

        self.assertEqual(FormData.objects.filter(form=self.form).count(), 1)
        self.assertFalse(FormData.objects.get(pk=row.pk).is_draft)

    def test_replay_finds_soft_deleted_row(self):
        key = "99999999-9999-9999-9999-999999999999"

        self.post_sync(submission_key=key)
        row = FormData.objects.filter(form=self.form).first()
        row.soft_delete()

        # The default manager hides soft-deleted rows; the unique index does
        # not. Looking up through objects instead of _base_manager would miss
        # this row, hit the index, and raise.
        response = self.post_sync(submission_key=key)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            FormData.objects_with_deleted.filter(
                submission_key=key
            ).count(),
            1,
        )
