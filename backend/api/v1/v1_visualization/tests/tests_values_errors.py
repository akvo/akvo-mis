from django.test.utils import override_settings
from rest_framework.test import APITestCase
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)
from api.v1.v1_visualization.dashboard_serializers import (
    ValuesFilterSerializer,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesErrorTestCases(VisualizationValuesTestMixin, APITestCase):
    """Test error handling and input validation for /visualization/values."""

    def test_missing_form_id(self):
        """form_id is required — returns 400."""
        response = self.client.get(f"{self.BASE_URL}")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("message", data)

    def test_invalid_form_id(self):
        """Non-existent form_id — 404, indistinguishable from
        another tenant's."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id=99999"
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_question_id(self):
        """Non-existent question_id — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&question_id=99999"
        )
        self.assertEqual(response.status_code, 400)

    def test_question_not_in_form(self):
        """question_id exists but belongs to a different form — returns 400."""
        from api.v1.v1_forms.models import Questions, QuestionGroup
        from api.v1.v1_forms.constants import QuestionTypes
        other_form = self.registration
        other_qg = QuestionGroup.objects.create(
            id=79999, form=other_form, name="other_qg",
        )
        other_q = Questions.objects.create(
            id=7999,
            question_group=other_qg,
            form=other_form,
            name="other_question",
            label="Other",
            type=QuestionTypes.number,
        )
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={other_q.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_question_type(self):
        """Text question type is not supported — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            f"&question_id={self.q_text.id}"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_group_by(self):
        """Invalid group_by value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&group_by=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_monitoring(self):
        """Invalid monitoring value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&monitoring=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_value_type(self):
        """Invalid value_type value — returns 400."""
        response = self.client.get(
            f"{self.BASE_URL}?form_id={self.monitoring.id}"
            "&value_type=invalid_value"
        )
        self.assertEqual(response.status_code, 400)

    def test_serializer_without_user_context_fails_loudly(self):
        """Constructing ValuesFilterSerializer with no context must
        raise instead of silently validating against `tenant IS
        NULL`. The view (dashboard_views.visualization_values) always
        passes context={"user": request.user}, so this exercises a
        caller that skips that — not reachable over HTTP, but worth
        pinning so the lookup cannot regress to a .get() that
        returns None unnoticed.
        """
        serializer = ValuesFilterSerializer(
            data={"form_id": self.monitoring.id},
        )
        with self.assertRaises(KeyError):
            serializer.is_valid()
