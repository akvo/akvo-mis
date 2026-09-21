from django.test import TestCase, override_settings

from api.v1.v1_data.functions import answer_fields
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import Organisation


@override_settings(USE_TZ=False, TEST_ENV=True)
class AnswerFieldsTestCase(TestCase):
    """The single answer type-dispatch.

    This used to be five copies across three serializers and two views.
    They drifted, so these tests pin the contract in one place.
    """

    def setUp(self):
        self.form = Forms.objects.create(name="Dispatch Form", version=1)
        self.group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )

    def question(self, qtype, **kwargs):
        return Questions.objects.create(
            form=self.form,
            question_group=self.group,
            name=f"q{qtype}",
            label=f"Question {qtype}",
            order=1,
            type=qtype,
            **kwargs,
        )

    def test_geo_goes_to_options(self):
        q = self.question(QuestionTypes.geo)
        self.assertEqual(
            answer_fields(q, [9.03, 38.74]), (None, None, [9.03, 38.74])
        )

    def test_option_goes_to_options(self):
        q = self.question(QuestionTypes.option)
        self.assertEqual(answer_fields(q, ["yes"]), (None, None, ["yes"]))

    def test_multiple_option_goes_to_options(self):
        q = self.question(QuestionTypes.multiple_option)
        self.assertEqual(
            answer_fields(q, ["a", "b"]), (None, None, ["a", "b"])
        )

    def test_text_goes_to_name(self):
        q = self.question(QuestionTypes.text)
        self.assertEqual(answer_fields(q, "hello"), ("hello", None, None))

    def test_autofield_goes_to_name(self):
        """The edit paths used to miss this and push a string into a
        FloatField."""
        q = self.question(QuestionTypes.autofield)
        self.assertEqual(answer_fields(q, "derived"), ("derived", None, None))

    def test_signature_goes_to_name(self):
        q = self.question(QuestionTypes.signature)
        self.assertEqual(answer_fields(q, "data:image/png;base64,x"),
                         ("data:image/png;base64,x", None, None))

    def test_number_goes_to_value(self):
        q = self.question(QuestionTypes.number)
        self.assertEqual(answer_fields(q, 42), (None, 42, None))

    def test_administration_cascade_keeps_label_and_id(self):
        """Both columns. The label for display, the id for joins."""
        level = Levels.objects.create(name="National", level=0)
        adm = Administration.objects.create(name="Ethiopia", level=level)
        q = self.question(
            QuestionTypes.cascade,
            api={"endpoint": "/api/v1/administration"},
        )
        self.assertEqual(answer_fields(q, adm.id), ("Ethiopia", adm.id, None))

    def test_organisation_cascade_keeps_label_only(self):
        org = Organisation.objects.create(name="Akvo")
        q = self.question(
            QuestionTypes.cascade,
            api={"endpoint": "/api/v1/organisations"},
        )
        self.assertEqual(answer_fields(q, org.id), ("Akvo", None, None))

    def test_missing_cascade_target_yields_none_name(self):
        q = self.question(
            QuestionTypes.cascade,
            api={"endpoint": "/api/v1/administration"},
        )
        self.assertEqual(answer_fields(q, 999999), (None, 999999, None))
