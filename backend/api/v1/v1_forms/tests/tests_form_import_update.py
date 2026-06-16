from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    normalize_form_definition,
    import_form_definition,
)
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_users.models import SystemUser


def _make_export_payload(name="Import Test Form", form_id=999001, type_=1):
    return {
        "metadata": {
            "format_version": 1,
            "exported_at": "2026-06-12T00:00:00Z",
            "source": "staging.mis.akvo.org",
        },
        "id": form_id,
        "name": name,
        "type": type_,
        "question_group": [
            {
                "id": 999100,
                "name": "main_group",
                "label": "Main",
                "order": 1,
                "question": [
                    {
                        "id": 999200,
                        "name": "full_name",
                        "label": "Full Name",
                        "type": "input",
                        "order": 1,
                        "questionGroupId": 999100,
                        "required": True,
                        "meta": True,
                        "dependency": None,
                        "displayOnly": False,
                        "option": [],
                    },
                    {
                        "id": 999201,
                        "name": "gender",
                        "label": "Gender",
                        "type": "option",
                        "order": 2,
                        "questionGroupId": 999100,
                        "required": True,
                        "dependency": [{"id": 999200, "options": ["yes"]}],
                        "displayOnly": False,
                        "option": [
                            {"label": "Male", "value": "male", "order": 1},
                            {"label": "Female", "value": "female", "order": 2},
                        ],
                    },
                ],
            }
        ],
    }


def _reset_pk_sequences():
    with connection.cursor() as cur:
        for tbl in ["form", "question_group", "question", "option"]:
            cur.execute(
                f"SELECT setval("
                f"pg_get_serial_sequence('{tbl}', 'id'),"
                f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                f"false)"
            )


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImportFormDefinitionUpdateTestCase(TestCase):
    """Tests for import_form_definition — update path."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        _reset_pk_sequences()
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()
        raw = _make_export_payload(form_id=777001)
        norm = normalize_form_definition(raw)
        self.existing_form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )

    def test_update_path_returns_updated_action(self):
        raw = _make_export_payload(
            form_id=self.existing_form.id, name="Updated Form"
        )
        norm = normalize_form_definition(raw)
        _, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "updated")

    def test_update_path_syncs_form_name(self):
        raw = _make_export_payload(
            form_id=self.existing_form.id, name="New Name"
        )
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.name, "New Name")
        self.assertEqual(form.id, self.existing_form.id)

    def test_update_path_does_not_change_status(self):
        original_status = self.existing_form.status
        raw = _make_export_payload(form_id=self.existing_form.id)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.status, original_status)

    def test_update_path_soft_deletes_absent_question(self):
        raw = _make_export_payload(form_id=self.existing_form.id)
        raw["question_group"][0]["question"] = [
            raw["question_group"][0]["question"][0]
        ]
        norm = normalize_form_definition(raw)
        import_form_definition(norm, self.user, mode="create_or_update")
        deleted_q = Questions.objects_deleted.filter(
            form=self.existing_form, name="gender"
        ).first()
        self.assertIsNotNone(deleted_q)
        self.assertIsNotNone(deleted_q.deleted_at)

    def test_update_path_does_not_duplicate_form(self):
        count_before = Forms.objects.filter(
            id=self.existing_form.id
        ).count()
        raw = _make_export_payload(form_id=self.existing_form.id)
        norm = normalize_form_definition(raw)
        import_form_definition(norm, self.user, mode="create_or_update")
        count_after = Forms.objects.filter(
            id=self.existing_form.id
        ).count()
        self.assertEqual(count_before, count_after)
