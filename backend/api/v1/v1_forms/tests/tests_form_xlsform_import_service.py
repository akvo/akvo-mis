import io
import json
import tempfile
from unittest.mock import patch

import openpyxl
from django.test import TestCase

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.services.xlsform_export import generate_xlsform
from api.v1.v1_forms.services.xlsform_import import (
    build_form_payload,
    parse_relevant_expression,
    parse_xlsform,
    validate_preflight,
)
from api.v1.v1_forms.tasks import import_xlsform_job
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_users.models import SystemUser


def _build_test_workbook(
    survey_rows,
    choices_rows=None,
    settings_row=None,
    survey_headers=None,
    choices_headers=None,
    settings_headers=None,
) -> io.BytesIO:
    """Helper to create an in-memory openpyxl workbook."""
    wb = openpyxl.Workbook()

    ws_survey = wb.active
    ws_survey.title = "survey"
    s_headers = survey_headers or [
        "type",
        "name",
        "label",
        "required",
        "hint",
        "relevant",
        "constraint",
        "appearance",
        "body::accept",
    ]
    ws_survey.append(s_headers)
    for row in survey_rows:
        ws_survey.append(row)

    if choices_rows is not None:
        ws_choices = wb.create_sheet(title="choices")
        c_headers = choices_headers or ["list_name", "name", "label"]
        ws_choices.append(c_headers)
        for row in choices_rows:
            ws_choices.append(row)

    if settings_row is not None:
        ws_settings = wb.create_sheet(title="settings")
        st_headers = settings_headers or [
            "form_title",
            "form_id",
            "version",
            "default_language",
        ]
        ws_settings.append(st_headers)
        ws_settings.append(settings_row)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


class XLSFormImportServiceTestCase(TestCase):
    def test_parse_basic_types(self):
        survey_rows = [
            ["text", "q_text", "Text", "no", None, None, None, None, None],
            ["integer", "q_int", "Int", "no", None, None, None, None, None],
            ["decimal", "q_dec", "Dec", "no", None, None, None, None, None],
            ["date", "q_date", "Date", "no", None, None, None, None, None],
            ["geopoint", "q_geo", "Geo", "no", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        self.assertEqual(parsed["total_questions"], 5)
        self.assertEqual(len(parsed["question_groups"]), 1)
        questions = parsed["question_groups"][0]["question"]

        self.assertEqual(questions[0]["type"], "text")
        self.assertEqual(questions[0]["name"], "q_text")

        self.assertEqual(questions[1]["type"], "number")
        self.assertEqual(questions[1]["name"], "q_int")
        self.assertEqual(questions[1]["rule"], {"allowDecimal": False})

        self.assertEqual(questions[2]["type"], "number")
        self.assertEqual(questions[2]["name"], "q_dec")
        self.assertEqual(questions[2]["rule"], {"allowDecimal": True})

        self.assertEqual(questions[3]["type"], "date")
        self.assertEqual(questions[4]["type"], "geo")

    def test_parse_signature(self):
        survey_rows = [
            ["image", "q_sig", "Sig", "no", None, None, None, "signature", ""],
            ["image", "q_img", "Photo", "no", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["type"], "signature")
        self.assertEqual(questions[1]["type"], "image")

    def test_parse_select_one_and_multiple(self):
        survey_rows = [
            [
                "select_one gender_list",
                "gender",
                "Gender",
                "yes",
                None,
                None,
                None,
                None,
                None,
            ],
            [
                "select_multiple hob_list",
                "hobbies",
                "Hobbies",
                "no",
                None,
                None,
                None,
                None,
                None,
            ],
        ]
        choices_rows = [
            ["gender_list", "male", "Male"],
            ["gender_list", "female", "Female"],
            ["hob_list", "reading", "Reading"],
            ["hob_list", "sports", "Sports"],
        ]
        stream = _build_test_workbook(survey_rows, choices_rows=choices_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["type"], "option")
        self.assertEqual(len(questions[0]["option"]), 2)
        self.assertEqual(questions[0]["option"][0]["value"], "male")
        self.assertEqual(questions[0]["option"][0]["label"], "Male")
        self.assertEqual(questions[0]["required"], True)

        self.assertEqual(questions[1]["type"], "multiple_option")
        self.assertEqual(len(questions[1]["option"]), 2)
        self.assertEqual(questions[1]["option"][1]["value"], "sports")

    def test_parse_or_other(self):
        survey_rows = [
            [
                "select_one fruit_list or_other",
                "fruit",
                "Fruit",
                "no",
                None,
                None,
                None,
                None,
                None,
            ],
        ]
        choices_rows = [
            ["fruit_list", "apple", "Apple"],
        ]
        stream = _build_test_workbook(survey_rows, choices_rows=choices_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        opts = questions[0]["option"]
        self.assertEqual(len(opts), 2)
        self.assertEqual(opts[0]["value"], "apple")
        self.assertEqual(opts[1]["value"], "other")
        self.assertTrue(opts[1]["other"])

    def test_parse_cascade(self):
        survey_rows = [
            [
                "select_one_from_file administration.csv",
                "admin_loc",
                "Location",
                "no",
                None,
                None,
                None,
                None,
                None,
            ],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["type"], "cascade")

    def test_parse_attachment_and_file_accept(self):
        survey_rows = [
            ["file", "doc", "Doc", "no", None, None, None, None, ".pdf,.docx"],
            [
                "file",
                "photo",
                "Photo",
                "no",
                None,
                None,
                None,
                None,
                "image/*,.jpg,.png",
            ],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["type"], "attachment")
        self.assertEqual(
            questions[0]["rule"]["allowedFileTypes"], ["pdf", "docx"]
        )
        self.assertEqual(
            questions[1]["rule"]["allowedFileTypes"], ["jpg", "png"]
        )

    def test_parse_groups(self):
        survey_rows = [
            [
                "begin_group",
                "g_personal",
                "Personal Info",
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            ["text", "name", "Full Name", "no", None, None, None, None, None],
            ["end_group", None, None, None, None, None, None, None, None],
            [
                "begin_group",
                "g_contact",
                "Contact Details",
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            ["text", "email", "Email", "no", None, None, None, None, None],
            ["end_group", None, None, None, None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        self.assertEqual(len(parsed["question_groups"]), 2)
        self.assertEqual(parsed["question_groups"][0]["name"], "g_personal")
        self.assertEqual(
            parsed["question_groups"][0]["label"], "Personal Info"
        )
        self.assertEqual(len(parsed["question_groups"][0]["question"]), 1)

        self.assertEqual(parsed["question_groups"][1]["name"], "g_contact")
        self.assertEqual(len(parsed["question_groups"][1]["question"]), 1)

    def test_parse_constraint(self):
        survey_rows = [
            [
                "integer",
                "age",
                "Age",
                "no",
                None,
                None,
                ". >= 18 and . <= 65",
                None,
                None,
            ],
            [
                "decimal",
                "score",
                "Score",
                "no",
                None,
                None,
                ". >= 0.5",
                None,
                None,
            ],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["rule"]["min"], 18)
        self.assertEqual(questions[0]["rule"]["max"], 65)
        self.assertEqual(questions[1]["rule"]["min"], 0.5)

    def test_parse_translations(self):
        survey_headers = [
            "type",
            "name",
            "label::English (en)",
            "label::French (fr)",
            "hint::English (en)",
            "hint::French (fr)",
        ]
        survey_rows = [
            [
                "text",
                "fav_color",
                "Favorite Color",
                "Couleur préférée",
                "Pick one",
                "Choisissez-en un",
            ],
        ]
        choices_headers = [
            "list_name",
            "name",
            "label::English (en)",
            "label::French (fr)",
        ]
        choices_rows = [
            ["color_list", "red", "Red", "Rouge"],
        ]
        settings_headers = ["form_title", "default_language"]
        settings_row = ["Multilingual Survey", "English (en)"]

        stream = _build_test_workbook(
            survey_rows,
            choices_rows=choices_rows,
            settings_row=settings_row,
            survey_headers=survey_headers,
            choices_headers=choices_headers,
            settings_headers=settings_headers,
        )
        parsed = parse_xlsform(stream)

        self.assertEqual(parsed["form_name"], "Multilingual Survey")
        self.assertEqual(parsed["default_language"], "en")
        self.assertIn("fr", parsed["languages"])

        q = parsed["question_groups"][0]["question"][0]
        self.assertEqual(q["label"], "Favorite Color")
        self.assertEqual(q["tooltip"], "Pick one")
        self.assertIsNotNone(q["translations"])
        self.assertEqual(q["translations"][0]["language"], "fr")
        self.assertEqual(q["translations"][0]["label"], "Couleur préférée")
        self.assertEqual(q["translations"][0]["tooltip"], "Choisissez-en un")

    def test_parse_relevant_selected(self):
        name_to_id = {"has_car": 1, "car_type": 2}
        expr = "selected(${has_car}, 'yes')"
        deps, rule, warn = parse_relevant_expression(expr, name_to_id)

        self.assertIsNone(warn)
        self.assertEqual(rule, "AND")
        self.assertEqual(deps, [{"id": 1, "options": ["yes"]}])

    def test_parse_relevant_selected_multi_or(self):
        name_to_id = {"has_vehicle": 1}
        expr = (
            "(selected(${has_vehicle}, 'car') or "
            "selected(${has_vehicle}, 'bike'))"
        )
        deps, rule, warn = parse_relevant_expression(expr, name_to_id)

        self.assertIsNone(warn)
        self.assertEqual(deps, [{"id": 1, "options": ["car", "bike"]}])

    def test_parse_relevant_min_max(self):
        name_to_id = {"age": 5}
        expr = "${age} >= 18 and ${age} <= 65"
        deps, rule, warn = parse_relevant_expression(expr, name_to_id)

        self.assertIsNone(warn)
        self.assertEqual(rule, "AND")
        self.assertEqual(deps, [{"id": 5, "min": 18, "max": 65}])

    def test_parse_relevant_equal_and_not_equal(self):
        name_to_id = {"status": 3, "income": 4}
        expr_eq = "${status} = 'employed'"
        deps_eq, _, warn_eq = parse_relevant_expression(expr_eq, name_to_id)
        self.assertIsNone(warn_eq)
        self.assertEqual(deps_eq, [{"id": 3, "equal": "employed"}])

        expr_neq = "${status} != 'unemployed' and string-length(${status}) > 0"
        deps_neq, _, warn_neq = parse_relevant_expression(expr_neq, name_to_id)
        self.assertIsNone(warn_neq)
        self.assertEqual(deps_neq, [{"id": 3, "notEqual": "unemployed"}])

    def test_parse_relevant_or_rule(self):
        name_to_id = {"q1": 1, "q2": 2}
        expr = "${q1} = 'yes' or ${q2} = 'yes'"
        deps, rule, warn = parse_relevant_expression(expr, name_to_id)

        self.assertIsNone(warn)
        self.assertEqual(rule, "OR")
        self.assertEqual(len(deps), 2)
        self.assertEqual(deps[0], {"id": 1, "equal": "yes"})
        self.assertEqual(deps[1], {"id": 2, "equal": "yes"})

    def test_parse_relevant_unrecognized(self):
        name_to_id = {"q1": 1}
        expr = "count-selected(${q1}) > 2"
        deps, rule, warn = parse_relevant_expression(expr, name_to_id)

        self.assertIsNotNone(warn)
        self.assertEqual(deps, [])

    def test_parse_skip_unsupported(self):
        survey_rows = [
            ["calculate", "calc_1", "Calc", None, None, None, None, None],
            ["note", "note_1", "Note", None, None, None, None, None],
            ["text", "q_real", "Real", "no", None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        self.assertEqual(parsed["total_questions"], 1)
        self.assertEqual(len(parsed["skipped_rows"]), 2)
        self.assertIn("calculate", parsed["skipped_rows"][0]["message"])

    def test_preflight_error_no_survey_sheet(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "not_survey"
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)

        with self.assertRaises(ValueError):
            parse_xlsform(stream)

    def test_preflight_error_no_questions(self):
        survey_rows = [
            ["calculate", "calc_1", "Calc", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)
        errors, warnings = validate_preflight(parsed)

        self.assertTrue(
            any("No valid questions found" in e["message"] for e in errors)
        )

    def test_preflight_error_duplicate_names(self):
        survey_rows = [
            ["text", "dup_name", "Q1", "no", None, None, None, None, None],
            ["text", "dup_name", "Q2", "no", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)
        errors, warnings = validate_preflight(parsed)

        self.assertTrue(
            any("Duplicate question name" in e["message"] for e in errors)
        )

    def test_build_form_payload(self):
        survey_rows = [
            ["text", "q1", "Q1", "no", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)
        parsed = parse_xlsform(stream)

        # 1. Registration
        payload_reg = build_form_payload(parsed, form_type="registration")
        self.assertEqual(payload_reg["type"], FormTypes.registration)
        self.assertIsNone(payload_reg["parent_hint"])

        # 2. Monitoring with parent_id
        payload_mon = build_form_payload(
            parsed, form_type="monitoring", parent_id=42
        )
        self.assertEqual(payload_mon["type"], FormTypes.monitoring)
        self.assertEqual(payload_mon["parent_hint"], {"id": 42})

    def test_round_trip_export_and_import(self):
        dict_payload = {
            "id": 101,
            "name": "Household Profile Form",
            "version": 2,
            "languages": ["en", "fr"],
            "defaultLanguage": "en",
            "question_group": [
                {
                    "id": 1,
                    "name": "demographics",
                    "label": "Demographics",
                    "question": [
                        {
                            "id": 10,
                            "name": "full_name",
                            "label": "Full Name",
                            "type": QuestionTypes.text,
                            "required": True,
                        },
                        {
                            "id": 20,
                            "name": "age",
                            "label": "Age",
                            "type": QuestionTypes.number,
                            "rule": {
                                "min": 18,
                                "max": 100,
                                "allowDecimal": False,
                            },
                        },
                        {
                            "id": 30,
                            "name": "gender",
                            "label": "Gender",
                            "type": QuestionTypes.option,
                            "option": [
                                {"label": "Female", "value": "female"},
                                {"label": "Male", "value": "male"},
                            ],
                        },
                    ],
                }
            ],
        }

        stream, skipped = generate_xlsform(dict_payload)
        self.assertEqual(skipped, [])

        parsed = parse_xlsform(stream)
        self.assertEqual(parsed["form_name"], "Household Profile Form")
        self.assertEqual(parsed["version"], 2)
        self.assertEqual(parsed["total_questions"], 3)

        questions = parsed["question_groups"][0]["question"]
        self.assertEqual(questions[0]["name"], "full_name")
        self.assertEqual(questions[0]["type"], "text")
        self.assertTrue(questions[0]["required"])

        self.assertEqual(questions[1]["name"], "age")
        self.assertEqual(questions[1]["type"], "number")
        self.assertEqual(questions[1]["rule"]["min"], 18)
        self.assertEqual(questions[1]["rule"]["max"], 100)

        self.assertEqual(questions[2]["name"], "gender")
        self.assertEqual(questions[2]["type"], "option")
        self.assertEqual(len(questions[2]["option"]), 2)

    def test_import_xlsform_job_success(self):
        user = SystemUser.objects.create(
            email="import_test_user@akvo.org",
            first_name="Import",
            last_name="User",
        )
        survey_rows = [
            ["text", "fav_sport", "Sport", "yes", None, None, None, None],
        ]
        stream = _build_test_workbook(
            survey_rows,
            settings_row=["Sport Survey", "sport_form", "1", "English (en)"],
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            tf.write(stream.getvalue())
            tf.flush()
            temp_path = tf.name

        job = Jobs.objects.create(
            type=JobTypes.import_form,
            status=JobStatus.on_progress,
            user=user,
            info={
                "file": "sport.xlsx",
                "form_type": "registration",
                "parent_id": None,
            },
        )

        with patch("api.v1.v1_forms.tasks.download", return_value=temp_path):
            import_xlsform_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.done)
        res = json.loads(job.result)
        self.assertIn("form_id", res)
        self.assertEqual(res["form_name"], "Sport Survey")

        # Verify created form in DB
        created_form = Forms.objects.get(id=res["form_id"])
        self.assertEqual(created_form.name, "Sport Survey")
        self.assertEqual(created_form.type, FormTypes.registration)
        self.assertEqual(created_form.form_question_group.count(), 1)
        self.assertEqual(created_form.form_questions.count(), 1)

    def test_import_xlsform_job_read_error(self):
        user = SystemUser.objects.create(
            email="read_err_user@akvo.org",
            first_name="Read",
            last_name="User",
        )
        job = Jobs.objects.create(
            type=JobTypes.import_form,
            status=JobStatus.on_progress,
            user=user,
            info={"file": "missing.xlsx"},
        )

        with patch(
            "api.v1.v1_forms.tasks.download",
            side_effect=FileNotFoundError("File not found on storage"),
        ):
            import_xlsform_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.failed)
        res = json.loads(job.result)
        self.assertEqual(res[0]["code"], "file_read_error")

    def test_import_xlsform_job_preflight_error(self):
        user = SystemUser.objects.create(
            email="preflight_err_user@akvo.org",
            first_name="Preflight",
            last_name="User",
        )
        survey_rows = [
            ["calculate", "calc_only", "Calc", None, None, None, None, None],
        ]
        stream = _build_test_workbook(survey_rows)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            tf.write(stream.getvalue())
            tf.flush()
            temp_path = tf.name

        job = Jobs.objects.create(
            type=JobTypes.import_form,
            status=JobStatus.on_progress,
            user=user,
            info={"file": "empty.xlsx"},
        )

        with patch("api.v1.v1_forms.tasks.download", return_value=temp_path):
            import_xlsform_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.failed)
        res = json.loads(job.result)
        self.assertTrue(
            any(
                "No valid questions found" in err.get("message", "")
                for err in res
            )
        )
