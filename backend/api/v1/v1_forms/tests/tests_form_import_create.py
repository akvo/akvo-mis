from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.functions import (
    normalize_form_definition,
    import_form_definition,
)
from api.v1.v1_forms.models import QuestionGroup, Questions
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
class ImportFormDefinitionCreateTestCase(TestCase):
    """Tests for import_form_definition — create path."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        _reset_pk_sequences()
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    def test_create_path_produces_draft_form(self):
        raw = _make_export_payload(form_id=888001)
        norm = normalize_form_definition(raw)
        form, action = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(action, "created")
        self.assertEqual(form.status, FormStatus.draft)

    def test_create_path_preserves_form_id_when_free(self):
        raw = _make_export_payload(form_id=888002)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.id, 888002)

    def test_create_path_preserves_question_ids_when_free(self):
        raw = _make_export_payload(form_id=888003)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        q_ids = list(
            Questions.objects.filter(form=form).values_list("id", flat=True)
        )
        self.assertIn(999200, q_ids)
        self.assertIn(999201, q_ids)

    def test_create_path_creates_question_groups(self):
        raw = _make_export_payload(form_id=888004)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(
            QuestionGroup.objects.filter(form=form).count(), 1
        )

    def test_create_path_creates_options(self):
        raw = _make_export_payload(form_id=888005)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        gender_q = Questions.objects.get(form=form, name="gender")
        self.assertEqual(gender_q.options.count(), 2)

    def test_create_copy_mode_assigns_new_form_id(self):
        raw = _make_export_payload(form_id=888006)
        norm = normalize_form_definition(raw)
        form, action = import_form_definition(
            norm, self.user, mode="create_copy"
        )
        self.assertEqual(action, "copied")
        self.assertNotEqual(form.id, 888006)

    def test_create_copy_mode_remaps_dependency_refs(self):
        raw = _make_export_payload(form_id=888007)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_copy"
        )
        gender_q = Questions.objects.get(form=form, name="gender")
        full_name_q = Questions.objects.get(form=form, name="full_name")
        deps = gender_q.dependency or []
        dep_ids = [d["id"] for d in deps]
        self.assertIn(full_name_q.id, dep_ids)
        self.assertNotIn(999200, dep_ids)

    def test_import_sets_created_by(self):
        raw = _make_export_payload(form_id=888008)
        norm = normalize_form_definition(raw)
        form, _ = import_form_definition(
            norm, self.user, mode="create_or_update"
        )
        self.assertEqual(form.created_by, self.user)
