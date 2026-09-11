from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from api.v1.v1_data.functions import answer_fields
from api.v1.v1_data.serializers import SubmitFormDataAnswerSerializer
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions


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
