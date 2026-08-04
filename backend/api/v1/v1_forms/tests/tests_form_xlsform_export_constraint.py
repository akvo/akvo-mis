from unittest.mock import MagicMock

from django.test import TestCase

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.services.xlsform_export import (
    _build_constraint,
    _build_survey_rows,
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


class XLSFormExportConstraintTestCase(TestCase):
    def test_build_constraint(self):
        # min only
        c_min, m_min = _build_constraint({"min": 10})
        self.assertEqual(c_min, ". >= 10")
        self.assertEqual(m_min, "Value must be at least 10")

        # max only
        c_max, m_max = _build_constraint({"max": 100})
        self.assertEqual(c_max, ". <= 100")
        self.assertEqual(m_max, "Value must be at most 100")

        # min and max range
        c_range, m_range = _build_constraint({"min": 10, "max": 100})
        self.assertEqual(c_range, ". >= 10 and . <= 100")
        self.assertEqual(m_range, "Value must be between 10 and 100")

        # None rule or empty dict
        self.assertEqual(_build_constraint(None), (None, None))
        self.assertEqual(_build_constraint({}), (None, None))

    def test_survey_rows_t003_multilingual_addons_and_skipped_collection(self):
        q_valid = DummyObject(
            id=1,
            name="q_text",
            type=QuestionTypes.text,
            label="English Label",
            tooltip=None,
            rule={
                "addon_before": "Pre",
                "addon_after": "Post",
            },  # dropped silently
            translations={"es": {"label": "Spanish Label"}},
        )

        q_skipped = DummyObject(
            id=2,
            name="q_tree",
            type=QuestionTypes.tree,  # unsupported type
            label="Tree Question",
            tooltip=None,
            rule={},
            translations=None,
        )

        g = DummyObject(
            name="grp", repeat=False, question_group_question=MagicMock()
        )
        g.question_group_question.all.return_value = [q_valid, q_skipped]

        f = DummyObject(form_question_group=MagicMock())
        f.form_question_group.all.return_value = [g]

        qmap = {
            1: {"name": "q_text", "type": QuestionTypes.text},
            2: {"name": "q_tree", "type": QuestionTypes.tree},
        }

        rows, skipped = _build_survey_rows(f, qmap, ["es"])

        # Unsupported type collected in skipped list
        self.assertEqual(skipped, ["q_tree"])

        # Check valid question row
        q_row = next((r for r in rows if r.get("name") == "q_text"), None)
        self.assertIsNotNone(q_row)
        self.assertEqual(q_row["label"], "English Label")
        self.assertEqual(q_row["label::es"], "Spanish Label")

        # Check addons are omitted from row fields
        self.assertNotIn("addon_before", q_row)
        self.assertNotIn("addon_after", q_row)
