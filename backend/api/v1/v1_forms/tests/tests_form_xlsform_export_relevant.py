from django.test import TestCase

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.services.xlsform_export import _build_relevant_expression


class DummyObject:
    def __init__(self, **kwargs):
        self.dependency = None
        self.dependency_rule = None
        self.rule = None
        self.tooltip = None
        self.translations = None
        self.api = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class XLSFormExportRelevantTestCase(TestCase):
    def test_build_relevant_expression_single_and_multiple_options(self):
        q_map = {
            10: {"name": "water_source", "type": QuestionTypes.option},
        }

        # Single option selected
        q1 = DummyObject(dependency=[{"id": 10, "options": ["pipe"]}])
        self.assertEqual(
            _build_relevant_expression(q1, q_map),
            "selected(${water_source}, 'pipe')",
        )

        # Multiple options selected (OR within question)
        q2 = DummyObject(dependency=[{"id": 10, "options": ["pipe", "well"]}])
        self.assertEqual(
            _build_relevant_expression(q2, q_map),
            "(selected(${water_source}, 'pipe') or selected(${water_source}, 'well'))",  # noqa
        )

    def test_build_relevant_expression_min_max_equal_notequal(self):
        q_map = {
            20: {"name": "age", "type": QuestionTypes.number},
            21: {"name": "city", "type": QuestionTypes.text},
        }

        # min & max numeric bounds
        q_min = DummyObject(dependency=[{"id": 20, "min": 18}])
        self.assertEqual(
            _build_relevant_expression(q_min, q_map), "${age} >= 18"
        )

        q_max = DummyObject(dependency=[{"id": 20, "max": 65}])
        self.assertEqual(
            _build_relevant_expression(q_max, q_map), "${age} <= 65"
        )

        q_range = DummyObject(dependency=[{"id": 20, "min": 18, "max": 65}])
        self.assertEqual(
            _build_relevant_expression(q_range, q_map),
            "${age} >= 18 and ${age} <= 65",
        )

        # equal & notEqual
        q_eq = DummyObject(dependency=[{"id": 21, "equal": "Jakarta"}])
        self.assertEqual(
            _build_relevant_expression(q_eq, q_map), "${city} = 'Jakarta'"
        )

        q_neq = DummyObject(dependency=[{"id": 21, "notEqual": "Jakarta"}])
        self.assertEqual(
            _build_relevant_expression(q_neq, q_map),
            "${city} != 'Jakarta' and string-length(${city}) > 0",
        )

    def test_build_relevant_expression_combinators_and_unresolvable_id(self):
        q_map = {
            1: {"name": "has_pipe", "type": QuestionTypes.option},
            2: {"name": "family_members", "type": QuestionTypes.number},
        }

        # Default AND combinator across multiple dependency rules
        q_and = DummyObject(
            dependency=[{"id": 1, "options": ["yes"]}, {"id": 2, "min": 3}],
            dependency_rule="AND",
        )
        self.assertEqual(
            _build_relevant_expression(q_and, q_map),
            "selected(${has_pipe}, 'yes') and ${family_members} >= 3",
        )

        # OR combinator
        q_or = DummyObject(
            dependency=[{"id": 1, "options": ["yes"]}, {"id": 2, "min": 3}],
            dependency_rule="OR",
        )
        self.assertEqual(
            _build_relevant_expression(q_or, q_map),
            "selected(${has_pipe}, 'yes') or ${family_members} >= 3",
        )

        # Unresolvable ID (question ID not in map) -> skipped
        q_unresolved = DummyObject(
            dependency=[{"id": 999, "options": ["yes"]}, {"id": 2, "min": 3}]
        )
        self.assertEqual(
            _build_relevant_expression(q_unresolved, q_map),
            "${family_members} >= 3",
        )

    def test_build_relevant_expression_edge_cases(self):
        q_map = {1: {"name": "valid_q", "type": QuestionTypes.number}}

        # Empty dependency
        self.assertEqual(
            _build_relevant_expression(DummyObject(dependency=[]), q_map), ""
        )
        self.assertEqual(
            _build_relevant_expression(DummyObject(dependency=None), q_map), ""
        )

        # Dependency entry without conditions
        q_empty_entry = DummyObject(dependency=[{"id": 1}])
        self.assertEqual(_build_relevant_expression(q_empty_entry, q_map), "")
