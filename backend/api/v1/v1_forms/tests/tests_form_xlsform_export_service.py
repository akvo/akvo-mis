import openpyxl
from unittest.mock import MagicMock

from django.test import TestCase

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.services.xlsform_export import (
    _map_type,
    _build_question_map,
    _build_settings_row,
    _build_choices_rows,
    _build_survey_rows,
    generate_xlsform,
)


class DummyObject:
    def __init__(self, **kwargs):
        self.label = None
        self.rule = None
        self.tooltip = None
        self.translations = None
        self.api = None
        self.repeatable = False
        self.required = False
        for k, v in kwargs.items():
            setattr(self, k, v)
            if k == "repeat":
                self.repeatable = bool(v)
            if k == "rule" and isinstance(v, dict) and "required" in v:
                self.required = bool(v["required"])


class XLSFormExportServiceTestCase(TestCase):
    def test_map_type_all_17_types(self):
        # 1. Input / Text
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.text)), ("text", None)
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.input)), ("text", None)
        )

        # 2. Number
        self.assertEqual(
            _map_type(
                DummyObject(
                    type=QuestionTypes.number, rule={"allowDecimal": True}
                )
            ),
            ("decimal", None),
        )
        self.assertEqual(
            _map_type(
                DummyObject(
                    type=QuestionTypes.number, rule={"allowDecimal": False}
                )
            ),
            ("integer", None),
        )

        # 3. Date
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.date)), ("date", None)
        )

        # 4. Option (Single & Multiple with or_other)
        opt_normal = DummyObject(other=False)
        opt_other = DummyObject(other=True)

        mock_mgr_normal = MagicMock()
        mock_mgr_normal.all.return_value = [opt_normal]

        mock_mgr_other = MagicMock()
        mock_mgr_other.all.return_value = [opt_normal, opt_other]

        q_opt = DummyObject(
            type=QuestionTypes.option,
            name="water_source",
            options=mock_mgr_normal,
        )
        self.assertEqual(
            _map_type(q_opt), ("select_one option_water_source", None)
        )

        q_opt_other = DummyObject(
            type=QuestionTypes.option,
            name="water_source",
            options=mock_mgr_other,
        )
        self.assertEqual(
            _map_type(q_opt_other),
            ("select_one option_water_source or_other", None),
        )

        q_mopt = DummyObject(
            type=QuestionTypes.multiple_option,
            name="amenities",
            options=mock_mgr_normal,
        )
        self.assertEqual(
            _map_type(q_mopt), ("select_multiple option_amenities", None)
        )

        q_mopt_other = DummyObject(
            type=QuestionTypes.multiple_option,
            name="amenities",
            options=mock_mgr_other,
        )
        self.assertEqual(
            _map_type(q_mopt_other),
            ("select_multiple option_amenities or_other", None),
        )

        # 5. Geo types
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.geo)), ("geopoint", None)
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.geoshape)),
            ("geoshape", None),
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.geotrace)),
            ("geotrace", None),
        )

        # 6. Media & File
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.image)), ("image", None)
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.attachment)),
            ("file", None),
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.signature)),
            ("image", "signature"),
        )

        # 7. Cascade
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.cascade)),
            ("select_one_from_file administration.csv", None),
        )

        # 8. Skipped types (tree, table, autofield)
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.tree)), (None, None)
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.table)), (None, None)
        )
        self.assertEqual(
            _map_type(DummyObject(type=QuestionTypes.autofield)), (None, None)
        )

        # 9. Fallback for unknown
        self.assertEqual(_map_type(DummyObject(type=999)), ("text", None))

    def test_build_question_map(self):
        q1 = DummyObject(id=1, name="q_one", type=QuestionTypes.text)
        q2 = DummyObject(id=2, name=None, type=QuestionTypes.number)
        g = DummyObject(question_group_question=MagicMock())
        g.question_group_question.all.return_value = [q1, q2]

        f = DummyObject(form_question_group=MagicMock())
        f.form_question_group.all.return_value = [g]

        qmap = _build_question_map(f)
        self.assertEqual(
            qmap,
            {
                1: {"name": "q_one", "type": QuestionTypes.text},
                2: {"name": "q_2", "type": QuestionTypes.number},
            },
        )

    def test_build_settings_row(self):
        f = DummyObject(
            id=42,
            name="Test Form",
            version=2,
            default_language="fr",
            languages=["fr", "en"],
        )
        settings = _build_settings_row(f)
        self.assertEqual(
            settings,
            {
                "form_title": "Test Form",
                "form_id": "form_42",
                "version": "2",
                "default_language": "French (fr)",
            },
        )

    def test_build_choices_rows_with_translations_and_other_filter(self):
        opt1 = DummyObject(
            id=10,
            value="yes",
            label="Yes",
            other=False,
            translations={"en": {"label": "Yes (EN)"}},
        )
        opt2 = DummyObject(
            id=11,
            value="other_val",
            label="Other",
            other=True,  # should be skipped
            translations=None,
        )

        mock_opts = MagicMock()
        mock_opts.all.return_value = [opt1, opt2]

        q = DummyObject(
            type=QuestionTypes.option,
            name="consent",
            options=mock_opts,
        )
        g = DummyObject(question_group_question=MagicMock())
        g.question_group_question.all.return_value = [q]

        f = DummyObject(form_question_group=MagicMock())
        f.form_question_group.all.return_value = [g]

        # Two languages: primary French (fr), secondary English (en)
        choices = _build_choices_rows(f, ["French (fr)", "English (en)"])
        self.assertEqual(len(choices), 1)
        self.assertEqual(
            choices[0],
            {
                "list_name": "option_consent",
                "name": "yes",
                "label::French (fr)": "Yes",  # opt.label (default)
                "label::English (en)": "Yes (EN)",  # from translations
            },
        )

    def test_build_survey_rows_repeatable_group_and_multilingual_hints(self):
        q_text = DummyObject(
            id=1,
            name="member_name",
            type=QuestionTypes.text,
            label="Member Name",
            tooltip={"text": "Enter full name"},
            rule={"required": True},
            translations={
                "en": {"label": "Member Name EN", "tooltip": "Full name EN"}
            },
        )

        g_repeat = DummyObject(
            name="household_members",
            repeat=True,
            question_group_question=MagicMock(),
        )
        g_repeat.question_group_question.all.return_value = [q_text]

        f = DummyObject(form_question_group=MagicMock())
        f.form_question_group.all.return_value = [g_repeat]

        q_map = {1: {"name": "member_name", "type": QuestionTypes.text}}
        # Two display-name langs: primary Spanish, secondary English
        rows, skipped = _build_survey_rows(
            f, q_map, ["Spanish (es)", "English (en)"]
        )

        self.assertEqual(len(skipped), 0)
        self.assertEqual(len(rows), 3)  # begin_repeat, question, end_repeat

        # 1. begin_repeat row
        self.assertEqual(rows[0]["type"], "begin_repeat")
        self.assertEqual(rows[0]["name"], "household_members")
        # Group has no label field — falls back to name
        self.assertIn("label::Spanish (es)", rows[0])

        # 2. question row
        q_row = rows[1]
        self.assertEqual(q_row["type"], "text")
        self.assertEqual(q_row["name"], "member_name")
        self.assertEqual(q_row["required"], "yes")
        # Default lang label
        self.assertEqual(q_row["label::Spanish (es)"], "Member Name")
        # Hint for default lang (from tooltip)
        self.assertEqual(q_row["hint::Spanish (es)"], "Enter full name")
        # Translation for English (en) ISO code 'en'
        self.assertEqual(q_row["label::English (en)"], "Member Name EN")
        self.assertEqual(q_row["hint::English (en)"], "Full name EN")

        # 3. end_repeat row
        self.assertEqual(rows[2]["type"], "end_repeat")

    def test_generate_xlsform_full_excel_verification(self):
        q1 = DummyObject(
            id=1,
            name="q_text",
            type=QuestionTypes.text,
            label="Text Question",
            rule={},
            translations=None,
            tooltip=None,
        )

        g = DummyObject(
            name="group_one", repeat=False, question_group_question=MagicMock()
        )
        g.question_group_question.all.return_value = [q1]

        # No explicit languages — should default to English (en)
        f = DummyObject(
            id=10,
            name="Test Form",
            version=1,
            default_language=None,
            languages=None,
            form_question_group=MagicMock(),
        )
        f.form_question_group.all.return_value = [g]

        stream, skipped = generate_xlsform(f)
        self.assertEqual(skipped, [])

        # Load generated workbook from stream
        wb = openpyxl.load_workbook(stream)
        self.assertEqual(wb.sheetnames, ["survey", "choices", "settings"])

        ws_survey = wb["survey"]
        ws_settings = wb["settings"]

        # Check headers of survey sheet — must use named language format
        headers = [cell.value for cell in ws_survey[1]]
        self.assertIn("type", headers)
        self.assertIn("name", headers)
        self.assertIn("label::English (en)", headers)
        self.assertNotIn("label", headers)  # bare label must not appear
        self.assertNotIn("label::en", headers)  # bare code must not appear

        # Check settings — default_language must be in display format
        settings_headers = [cell.value for cell in ws_settings[1]]
        settings_values = [cell.value for cell in ws_settings[2]]
        s_map = dict(zip(settings_headers, settings_values))
        self.assertEqual(s_map["form_title"], "Test Form")
        self.assertEqual(s_map["default_language"], "English (en)")

    def test_generate_xlsform_dict_payload_with_indonesian_translations(self):
        dict_payload = {
            "id": 4,
            "name": "Test Form 4",
            "version": 1,
            "languages": ["en", "id"],
            "defaultLanguage": "en",
            "translations": [
                {"language": "id", "name": "Formulir Percobaan 4"}
            ],
            "question_group": [
                {
                    "id": 44,
                    "name": "completeness_check",
                    "label": "Completeness Check",
                    "translations": [
                        {"language": "id", "name": "Memastikan Komplit"}
                    ],
                    "question": [
                        {
                            "id": 442,
                            "name": "name",
                            "label": "Your full name",
                            "type": "text",
                            "required": True,
                            "translations": [
                                {"language": "id", "name": "Nama lengkap"}
                            ],
                        }
                    ],
                }
            ],
        }

        stream, skipped = generate_xlsform(dict_payload)
        self.assertEqual(skipped, [])

        wb = openpyxl.load_workbook(stream)
        ws_survey = wb["survey"]

        headers = [cell.value for cell in ws_survey[1]]
        self.assertIn("label::English (en)", headers)
        self.assertIn("label::Indonesian (id)", headers)

        # Check row 2 (group)
        r2 = [cell.value for cell in ws_survey[2]]
        r2_map = dict(zip(headers, r2))
        self.assertEqual(r2_map["label::English (en)"], "Completeness Check")
        self.assertEqual(
            r2_map["label::Indonesian (id)"], "Memastikan Komplit"
        )

        # Check row 3 (question 'name')
        r3 = [cell.value for cell in ws_survey[3]]
        r3_map = dict(zip(headers, r3))
        self.assertEqual(r3_map["label::English (en)"], "Your full name")
        self.assertEqual(r3_map["label::Indonesian (id)"], "Nama lengkap")
