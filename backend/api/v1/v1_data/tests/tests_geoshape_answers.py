import json

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from api.v1.v1_data.functions import answer_fields, set_answer_data
from api.v1.v1_data.models import Answers, AnswerHistory
from api.v1.v1_data.serializers import SubmitFormDataAnswerSerializer
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_users.models import SystemUser
from utils.functions import get_answer_value, get_answer_history


# A plot near the equator and far from the prime meridian. Deliberately
# asymmetric: if latitude and longitude are ever swapped, these values
# land in the Indian Ocean instead of Ethiopia, and the assertion fails
# loudly. A fixture with similar lat and lon values would not catch it.
ADDIS_PLOT = [
    [9.03, 38.74],
    [9.04, 38.74],
    [9.04, 38.75],
    [9.03, 38.75],
]


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoshapeAnswerTestCase(TestCase):
    def setUp(self):
        self.form = Forms.objects.create(name="Plot Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )

    def question(self, qtype):
        return Questions.objects.create(
            form=self.form, question_group=self.group,
            name=f"q{qtype}", label="Plot boundary", order=1, type=qtype,
        )

    def test_geoshape_goes_to_options(self):
        q = self.question(QuestionTypes.geoshape)
        self.assertEqual(
            answer_fields(q, ADDIS_PLOT), (None, None, ADDIS_PLOT)
        )

    def test_geotrace_goes_to_options(self):
        q = self.question(QuestionTypes.geotrace)
        self.assertEqual(
            answer_fields(q, ADDIS_PLOT), (None, None, ADDIS_PLOT)
        )

    def test_stored_verbatim_latitude_first(self):
        """Axis-order regression guard. See spec D-2.

        The value must survive untouched: no GeoJSON wrapper, no axis
        swap, no closing vertex appended, no rounding. A swap does not
        crash; it produces plausible coordinates on another continent.
        """
        q = self.question(QuestionTypes.geoshape)
        _, _, options = answer_fields(q, ADDIS_PLOT)
        self.assertEqual(options, ADDIS_PLOT)
        self.assertEqual(options[0][0], 9.03)   # latitude
        self.assertEqual(options[0][1], 38.74)  # longitude
        self.assertEqual(len(options), 4)       # ring not closed
        self.assertNotEqual(options[0], options[-1])


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoshapeValidationTestCase(TestCase):
    def setUp(self):
        self.form = Forms.objects.create(name="Plot Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )
        self.q = Questions.objects.create(
            form=self.form, question_group=self.group, name="plot",
            label="Plot boundary", order=1, type=QuestionTypes.geoshape,
        )

    def validate(self, value, is_draft=False):
        serializer = SubmitFormDataAnswerSerializer(
            data={"question": self.q.id, "value": value},
            context={"is_draft": is_draft},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def test_a_coordinate_list_is_accepted(self):
        self.assertEqual(self.validate(ADDIS_PLOT)["value"], ADDIS_PLOT)

    def test_a_string_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate("9.03,38.74")

    def test_a_number_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(9.03)

    def test_a_string_is_rejected_on_drafts_too(self):
        with self.assertRaises(ValidationError):
            self.validate("9.03,38.74", is_draft=True)

    def test_a_flat_point_pair_is_rejected(self):
        """The `geo` point shape. A list, so the type check passes, but
        `point[0]` on a float raises in `bounding_box` and takes the
        whole form's datapoint-list down - repair path included."""
        with self.assertRaises(ValidationError):
            self.validate([9.03, 38.74])

    def test_a_non_numeric_pair_is_rejected(self):
        """No crash, worse: a string bounding box in the payload."""
        with self.assertRaises(ValidationError):
            self.validate([["a", "b"]])

    def test_a_wrong_arity_row_is_rejected(self):
        for bad in ([[1.0]], [[1.0, 2.0, 3.0, 4.0]]):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    self.validate(bad)

    def test_a_boolean_is_not_a_coordinate(self):
        """`isinstance(True, int)` is True, so a naive number check
        would let this through."""
        with self.assertRaises(ValidationError):
            self.validate([[True, False]])

    def test_malformed_rows_are_rejected_on_drafts_too(self):
        for bad in ([9.03, 38.74], [["a", "b"]], [[1.0]]):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    self.validate(bad, is_draft=True)

    # --- GEO-014: the optional third element (GPS accuracy) ---

    def test_a_vertex_may_carry_accuracy(self):
        """A three-element vertex used to be rejected as "wrong arity".
        GEO-014 D-2 makes the third element the vertex's GPS accuracy in
        metres."""
        walked = [[9.03, 38.74, 4.2], [9.04, 38.74, 6.8], [9.04, 38.75, 5.1]]
        self.assertEqual(self.validate(walked)["value"], walked)

    def test_a_ring_may_mix_measured_and_tapped_vertices(self):
        """One polygon can hold both: a boundary walked with GPS and
        corners tapped in by hand. Arity is per vertex, not per ring."""
        mixed = [[9.03, 38.74, 4.2], [9.04, 38.74], [9.04, 38.75, 5.1]]
        self.assertEqual(self.validate(mixed)["value"], mixed)

    def test_an_explicit_null_accuracy_is_accepted(self):
        """`null` and an absent element both mean "not measured", so
        refusing one of the two spellings would only surprise clients."""
        value = [[9.03, 38.74, None], [9.04, 38.74], [9.04, 38.75, None]]
        self.assertEqual(self.validate(value)["value"], value)

    def test_a_two_element_ring_is_still_accepted(self):
        """Every row written before GEO-014, and everything the webform
        produces, has two elements. It is valid permanently - there is no
        migration and no deprecation."""
        self.assertEqual(self.validate(ADDIS_PLOT)["value"], ADDIS_PLOT)

    def test_a_zero_accuracy_is_rejected(self):
        """ODK writes 0 for a manually placed point, meaning "not
        measured". Stored as a number it would read as *perfect*
        precision to GEO-007's adaptive threshold, making a traced
        polygon the most trusted geometry in the system. No real fix
        reads 0 m, so nothing legitimate is refused."""
        with self.assertRaises(ValidationError):
            self.validate([[9.03, 38.74, 0]])

    def test_a_negative_accuracy_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate([[9.03, 38.74, -1.5]])

    def test_a_non_numeric_accuracy_is_rejected(self):
        for bad in ("4.2", True, []):
            with self.subTest(accuracy=bad):
                with self.assertRaises(ValidationError):
                    self.validate([[9.03, 38.74, bad]])

    def test_a_flat_point_pair_is_still_rejected_with_the_wider_arity(self):
        """The guard `is_coordinate_ring` exists for. Widening arity to
        2-or-3 must not let `[9.03, 38.74]` through - it is caught by the
        list check on each member, never by the length."""
        with self.assertRaises(ValidationError):
            self.validate([9.03, 38.74])

    def test_accuracy_rings_are_accepted_on_drafts_too(self):
        walked = [[9.03, 38.74, 4.2], [9.04, 38.74], [9.04, 38.75, None]]
        self.assertEqual(
            self.validate(walked, is_draft=True)["value"], walked
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoshapeSeederTestCase(TestCase):
    def setUp(self):
        self.form = Forms.objects.create(name="Plot Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )
        self.q = Questions.objects.create(
            form=self.form, question_group=self.group, name="plot",
            label="Plot boundary", order=1, type=QuestionTypes.geoshape,
        )

    def test_seeder_produces_a_usable_polygon(self):
        name, value, option = set_answer_data(data=None, question=self.q)
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertGreaterEqual(len(option), 3)
        for lat, lon in option:
            self.assertTrue(-90 <= lat <= 90)
            self.assertTrue(-180 <= lon <= 180)
        self.assertNotEqual(option[0], option[-1])


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoshapeReadPathTestCase(TestCase):
    """The four type-dispatches that read an answer back.

    Before this branch a geoshape answer could not exist, so every one
    of these fell through to `Answers.value` and returned `None`. They
    are reachable now, and a `None` from any of them means two
    representations of one datapoint disagree.

    Nothing here needs saving: each dispatch reads only the question,
    the stored options and the index.
    """

    def setUp(self):
        self.form = Forms.objects.create(name="Plot Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )
        self.q = Questions.objects.create(
            form=self.form, question_group=self.group, name="plot",
            label="Plot boundary", order=1, type=QuestionTypes.geoshape,
        )
        self.answer = Answers(question=self.q, options=ADDIS_PLOT)

    def test_to_key_carries_the_polygon(self):
        """`to_key` builds the `{uuid}.json` file the datapoint list
        hands the device as `url`. A null here means the list says
        "polygon, here are its coordinates" and the file it points at
        says nothing for the same answer."""
        self.assertEqual(self.answer.to_key, {self.q.id: ADDIS_PLOT})

    def test_to_key_keeps_the_repeat_index_suffix(self):
        self.answer.index = 1
        self.assertEqual(
            self.answer.to_key, {f"{self.q.id}-1": ADDIS_PLOT}
        )

    def test_to_data_frame_renders_json(self):
        """One spreadsheet cell, and one that parses back."""
        self.assertEqual(
            self.answer.to_data_frame, {"plot": json.dumps(ADDIS_PLOT)}
        )

    def test_get_answer_value_returns_the_polygon(self):
        self.assertEqual(get_answer_value(self.answer), ADDIS_PLOT)

    def test_get_answer_history_returns_the_polygon(self):
        history = AnswerHistory(
            question=self.q,
            options=ADDIS_PLOT,
            created_by=SystemUser(first_name="Jane", last_name="Doe"),
        )
        self.assertEqual(get_answer_history(history)["value"], ADDIS_PLOT)

    def test_a_geotrace_reads_back_the_same_way(self):
        self.q.type = QuestionTypes.geotrace
        self.assertEqual(self.answer.to_key, {self.q.id: ADDIS_PLOT})
        self.assertEqual(get_answer_value(self.answer), ADDIS_PLOT)
