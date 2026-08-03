import openpyxl
from unittest import TestCase
from unittest.mock import MagicMock

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.services.xlsform_export import (
    _map_type,
    _build_question_map,
    _build_settings_row,
    generate_xlsform,
)


class DummyObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class XLSFormExportServiceTestCase(TestCase):
    def test_map_type_basic(self):
        q_text = DummyObject(
            type=QuestionTypes.input, rule=None, api=None, name="q_text"
        )
        self.assertEqual(_map_type(q_text), ("text", None))

        q_number_int = DummyObject(
            type=QuestionTypes.number,
            rule={"allowDecimal": False},
            api=None,
            name="q_num",
        )
        self.assertEqual(_map_type(q_number_int), ("integer", None))

        q_number_dec = DummyObject(
            type=QuestionTypes.number,
            rule={"allowDecimal": True},
            api=None,
            name="q_num",
        )
        self.assertEqual(_map_type(q_number_dec), ("decimal", None))

        q_sig = DummyObject(
            type=QuestionTypes.signature, rule=None, api=None, name="q_sig"
        )
        self.assertEqual(_map_type(q_sig), ("image", "signature"))

        q_skipped = DummyObject(
            type=QuestionTypes.tree, rule=None, api=None, name="q_tree"
        )
        self.assertEqual(_map_type(q_skipped), (None, None))

    def test_build_question_map(self):
        q1 = DummyObject(id=10, name="q_one", type=QuestionTypes.input)
        q2 = DummyObject(id=20, name="q_two", type=QuestionTypes.option)
        group = DummyObject(question_group_question=MagicMock())
        group.question_group_question.all.return_value = [q1, q2]

        form = DummyObject(form_question_group=MagicMock())
        form.form_question_group.all.return_value = [group]

        qmap = _build_question_map(form)
        self.assertEqual(
            qmap,
            {
                10: {"name": "q_one", "type": QuestionTypes.input},
                20: {"name": "q_two", "type": QuestionTypes.option},
            },
        )

    def test_build_settings_row(self):
        form = DummyObject(
            id=123,
            name="Test Form",
            version=2,
            default_language="en",
        )
        settings = _build_settings_row(form)
        self.assertEqual(
            settings,
            {
                "form_title": "Test Form",
                "form_id": "form_123",
                "version": "2",
                "default_language": "en",
            },
        )

    def test_generate_xlsform_structure(self):
        q1 = DummyObject(
            id=1,
            name="school_name",
            type=QuestionTypes.input,
            label="School Name",
            required=True,
            tooltip=None,
            translations=None,
            rule=None,
            api=None,
        )
        group = DummyObject(
            id=10,
            name="profile",
            label="School Profile",
            repeatable=False,
            translations=None,
            question_group_question=MagicMock(),
        )
        group.question_group_question.all.return_value = [q1]

        form = DummyObject(
            id=42,
            name="Sample Form",
            version=1,
            default_language="en",
            languages=["en"],
            form_question_group=MagicMock(),
        )
        form.form_question_group.all.return_value = [group]

        stream, skipped = generate_xlsform(form)
        self.assertEqual(skipped, [])

        wb = openpyxl.load_workbook(stream)
        self.assertIn("survey", wb.sheetnames)
        self.assertIn("choices", wb.sheetnames)
        self.assertIn("settings", wb.sheetnames)

        ws_survey = wb["survey"]
        rows = list(ws_survey.iter_rows(values_only=True))
        # Header row
        self.assertEqual(rows[0][0], "type")
        self.assertEqual(rows[0][1], "name")
        # begin_group row
        self.assertEqual(rows[1][0], "begin_group")
        self.assertEqual(rows[1][1], "profile")
        # question row
        self.assertEqual(rows[2][0], "text")
        self.assertEqual(rows[2][1], "school_name")
        # end_group row
        self.assertEqual(rows[3][0], "end_group")
