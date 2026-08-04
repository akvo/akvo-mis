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
            id=42, name="Test Form", version=2, default_language="fr"
        )
        settings = _build_settings_row(f)
        self.assertEqual(
            settings,
            {
                "form_title": "Test Form",
                "form_id": "form_42",
                "version": "2",
                "default_language": "fr",
            },
        )

    def test_build_choices_rows_with_translations_and_other_filter(self):
        opt1 = DummyObject(
            id=10,
            value="yes",
            label="Yes",
            other=False,
            translations={"fr": {"label": "Oui"}},
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

        choices = _build_choices_rows(f, ["fr"])
        self.assertEqual(len(choices), 1)
        self.assertEqual(
            choices[0],
            {
                "list_name": "option_consent",
                "name": "yes",
                "label": "Yes",
                "label::fr": "Oui",
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
                "es": {"label": "Nombre", "tooltip": "Nombre completo"}
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
        rows, skipped = _build_survey_rows(f, q_map, ["es"])

        self.assertEqual(len(skipped), 0)
        self.assertEqual(len(rows), 3)  # begin_repeat, question, end_repeat

        # 1. begin_repeat row
        self.assertEqual(rows[0]["type"], "begin_repeat")
        self.assertEqual(rows[0]["name"], "household_members")

        # 2. question row
        q_row = rows[1]
        self.assertEqual(q_row["type"], "text")
        self.assertEqual(q_row["name"], "member_name")
        self.assertEqual(q_row["required"], "yes")
        self.assertEqual(q_row["label::es"], "Nombre")
        self.assertEqual(q_row["hint::es"], "Nombre completo")

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

        f = DummyObject(
            id=10,
            name="Test Form",
            version=1,
            default_language="en",
            languages=["en"],
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

        # Check headers of survey sheet
        headers = [cell.value for cell in ws_survey[1]]
        self.assertIn("type", headers)
        self.assertIn("name", headers)
        self.assertIn("label::en", headers)

        # Check settings values
        settings_title = ws_settings.cell(row=2, column=1).value
        self.assertEqual(settings_title, "Test Form")
