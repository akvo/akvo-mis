import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, Questions, QuestionGroup
from api.v1.v1_users.models import SystemUser
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_profile.models import Administration


FORM_PAYLOAD = {
    "name": "CRUD Test Form",
    "type": 1,
    "approval_instructions": None,
    "parent": None,
    "question_group": [
        {
            "id": None,
            "name": "household_info",
            "label": "Household Information",
            "order": 1,
            "repeatable": False,
            "repeat_text": None,
            "question": [
                {
                    "id": None,
                    "order": 1,
                    "label": "Head of Household",
                    "short_label": None,
                    "name": "head_of_household",
                    "type": "input",
                    "meta": True,
                    "required": True,
                    "rule": None,
                    "dependency": None,
                    "dependency_rule": "AND",
                    "api": None,
                    "extra": None,
                    "tooltip": None,
                    "fn": None,
                    "pre": None,
                    "display_only": False,
                    "option": [],
                }
            ],
        }
    ],
}


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


@override_settings(USE_TZ=False, TEST_ENV=True)
class ManageFormSoftDeleteTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        with connection.cursor() as cur:
            for tbl in ["form", "question_group", "question", "option"]:
                cur.execute(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tbl}', 'id'),"
                    f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                    f"false)"
                )
        self.header = _login(self.client)
        self.admin = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def _create_form(self, payload=None):
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload or FORM_PAYLOAD),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201)
        return res.json()["id"]

    def _publish_form(self, form_id):
        self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )

    # ─────────────────────────────────────────────
    # Guard: cannot delete without allow_delete
    # ─────────────────────────────────────────────

    def test_update_cannot_delete_group_with_answers(self):
        """PUT removing an answered group returns 400."""
        form_id = self._create_form()
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        question = group.question_group_question.first()

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )
        Answers.objects.create(
            data=fd,
            question=question,
            name="Test Answer",
            created_by=self.admin,
        )

        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"] = []
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Can't delete", str(res.json()))

    def test_update_cannot_delete_question_with_answers(self):
        """PUT removing an answered question returns 400."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None,
            "order": 2,
            "label": "Age",
            "short_label": None,
            "name": "age",
            "type": "number",
            "meta": False,
            "required": False,
            "rule": None,
            "dependency": None,
            "dependency_rule": "AND",
            "api": None,
            "extra": None,
            "tooltip": None,
            "fn": None,
            "pre": None,
            "display_only": False,
            "option": [],
        })
        form_id = self._create_form(payload)
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="age")

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form,
            name="Test Submission",
            administration=adm,
            created_by=self.admin,
        )
        Answers.objects.create(
            data=fd,
            question=q2,
            value=25,
            created_by=self.admin,
        )

        update_payload = json.loads(json.dumps(FORM_PAYLOAD))
        update_payload["question_group"][0]["question_group_id"] = group.id
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(update_payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Can't delete", str(res.json()))

    def test_update_allow_delete_question_with_answers(self):
        """PUT allow_delete=true removes an answered question."""
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None, "order": 2, "label": "Age",
            "short_label": None, "name": "age", "type": "number",
            "meta": False, "required": False, "rule": None,
            "dependency": None, "dependency_rule": "AND",
            "api": None, "extra": None, "tooltip": None,
            "fn": None, "pre": None, "display_only": False, "option": [],
        })
        form_id = self._create_form(payload)
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="age")

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form, name="Test Submission",
            administration=adm, created_by=self.admin,
        )
        Answers.objects.create(
            data=fd, question=q2, value=25, created_by=self.admin,
        )

        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        q1 = detail["question_group"][0]["question"][0]
        update_payload = {
            "question_group": [{
                "id": detail["question_group"][0]["id"],
                "name": detail["question_group"][0]["name"],
                "label": detail["question_group"][0]["label"],
                "order": detail["question_group"][0]["order"],
                "repeatable": detail["question_group"][0]["repeatable"],
                "repeat_text": detail["question_group"][0]["repeat_text"],
                "question": [{**q1, "option": []}],
            }],
        }
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}?allow_delete=true",
            json.dumps(update_payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        questions = res.json()["question_group"][0]["question"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["name"], "head_of_household")

    # ─────────────────────────────────────────────
    # DB-level: soft-delete vs hard-delete
    # ─────────────────────────────────────────────

    def test_soft_delete_question_preserves_db_row(self):
        """
        PUT allow_delete=True soft-deletes the question: API hides it but
        the DB row survives with deleted_at set, preserving Answer FK validity.
        """
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None, "order": 2, "label": "Age",
            "short_label": None, "name": "age", "type": "number",
            "meta": False, "required": False, "rule": None,
            "dependency": None, "dependency_rule": "AND",
            "api": None, "extra": None, "tooltip": None,
            "fn": None, "pre": None, "display_only": False, "option": [],
        })
        form_id = self._create_form(payload)
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="age")
        q2_id = q2.id

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form, name="Submission",
            administration=adm, created_by=self.admin,
        )
        ans = Answers.objects.create(
            data=fd, question=q2, value=25, created_by=self.admin,
        )

        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        q1 = detail["question_group"][0]["question"][0]
        grp = detail["question_group"][0]
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}?allow_delete=true",
            json.dumps({
                "question_group": [{
                    "id": grp["id"],
                    "name": grp["name"],
                    "label": grp["label"],
                    "order": grp["order"],
                    "repeatable": grp["repeatable"],
                    "repeat_text": grp["repeat_text"],
                    "question": [{**q1, "option": []}],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            len(res.json()["question_group"][0]["question"]), 1
        )
        # DB row still exists with deleted_at set
        q2_db = Questions.objects_with_deleted.get(pk=q2_id)
        self.assertIsNotNone(
            q2_db.deleted_at,
            "Question must be soft-deleted, not hard-deleted",
        )
        # Answer FK intact
        self.assertTrue(Answers.objects.filter(pk=ans.id).exists())

    def test_soft_delete_group_with_allow_delete(self):
        """
        PUT allow_delete=True soft-deletes an entire group and its questions:
        DB rows survive with deleted_at set; Answer FK valid.
        """
        two_group_payload = {
            "name": "Two Group Form", "type": 1,
            "question_group": [
                {
                    "id": None, "name": "group_one", "label": "Group One",
                    "order": 1, "repeatable": False, "repeat_text": None,
                    "question": [{
                        "id": None, "order": 1, "label": "Q1",
                        "short_label": None, "name": "q1", "type": "input",
                        "meta": True, "required": True, "rule": None,
                        "dependency": None, "dependency_rule": "AND",
                        "api": None, "extra": None, "tooltip": None,
                        "fn": None, "pre": None, "display_only": False,
                        "option": [],
                    }],
                },
                {
                    "id": None, "name": "group_two", "label": "Group Two",
                    "order": 2, "repeatable": False, "repeat_text": None,
                    "question": [{
                        "id": None, "order": 1, "label": "Q2",
                        "short_label": None, "name": "q2", "type": "input",
                        "meta": False, "required": True, "rule": None,
                        "dependency": None, "dependency_rule": "AND",
                        "api": None, "extra": None, "tooltip": None,
                        "fn": None, "pre": None, "display_only": False,
                        "option": [],
                    }],
                },
            ],
        }
        form_id = self._create_form(two_group_payload)
        form = Forms.objects.get(pk=form_id)
        grp2 = form.form_question_group.get(name="group_two")
        grp2_id = grp2.id
        q2 = grp2.question_group_question.get(name="q2")
        q2_id = q2.id

        adm = Administration.objects.filter(level__level=1).first()
        fd = FormData.objects.create(
            form=form, name="Submission",
            administration=adm, created_by=self.admin,
        )
        ans = Answers.objects.create(
            data=fd, question=q2, created_by=self.admin,
        )

        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        grp1_detail = next(
            g for g in detail["question_group"] if g["name"] == "group_one"
        )
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}?allow_delete=true",
            json.dumps({
                "question_group": [{
                    "id": grp1_detail["id"],
                    "name": grp1_detail["name"],
                    "label": grp1_detail["label"],
                    "order": grp1_detail["order"],
                    "repeatable": grp1_detail["repeatable"],
                    "repeat_text": grp1_detail["repeat_text"],
                    "question": [{
                        **grp1_detail["question"][0], "option": []
                    }],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["question_group"]), 1)
        grp2_db = QuestionGroup.objects_with_deleted.get(pk=grp2_id)
        self.assertIsNotNone(grp2_db.deleted_at)
        q2_db = Questions.objects_with_deleted.get(pk=q2_id)
        self.assertIsNotNone(q2_db.deleted_at)
        self.assertTrue(Answers.objects.filter(pk=ans.id).exists())

    def test_hard_delete_question_row_is_gone(self):
        """
        PUT without allow_delete hard-deletes a question that has no answers:
        the DB row is completely removed, not soft-deleted.
        """
        payload = json.loads(json.dumps(FORM_PAYLOAD))
        payload["question_group"][0]["question"].append({
            "id": None, "order": 2, "label": "Age",
            "short_label": None, "name": "age", "type": "number",
            "meta": False, "required": False, "rule": None,
            "dependency": None, "dependency_rule": "AND",
            "api": None, "extra": None, "tooltip": None,
            "fn": None, "pre": None, "display_only": False, "option": [],
        })
        form_id = self._create_form(payload)
        form = Forms.objects.get(pk=form_id)
        group = form.form_question_group.first()
        q2 = group.question_group_question.get(name="age")
        q2_id = q2.id  # no answers for q2

        detail = self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        ).json()
        q1 = detail["question_group"][0]["question"][0]
        grp = detail["question_group"][0]
        res = self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps({
                "question_group": [{
                    "id": grp["id"],
                    "name": grp["name"],
                    "label": grp["label"],
                    "order": grp["order"],
                    "repeatable": grp["repeatable"],
                    "repeat_text": grp["repeat_text"],
                    "question": [{**q1, "option": []}],
                }],
            }),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(
            Questions.objects_with_deleted.filter(pk=q2_id).exists(),
            "Question with no answers must be hard-deleted, not soft-deleted",
        )
