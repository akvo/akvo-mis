from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from api.v1.v1_chatbot.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
)
from api.v1.v1_chatbot.utils import get_page_context
from api.v1.v1_users.models import SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class ChatbotTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = SystemUser.objects.create_user(
            email="test_chatbot@akvo.org",
            first_name="Chatbot",
            last_name="Tester",
            password="testpassword123",
        )

    def test_chatbot_get_page_context_segments(self):
        """Assert dynamic URL context derivation for various route shapes."""
        test_cases = [
            (
                "/control-center",
                "Control Center",
            ),
            (
                "/data",
                "Data Management",
            ),
            (
                "/control-center/form-builder/42/edit",
                "Form Builder — Edit",
            ),
            (
                "/control-center/master-data/administration",
                "Master Data — Administration",
            ),
            (
                "/control-center/approvals",
                "Approvals",
            ),
            (
                "/control-center/users/add",
                "Users — Add",
            ),
            (
                "/control-center/mobile-assignment",
                "Mobile Assignment",
            ),
            (
                "/control-center/roles/10/edit",
                "Roles — Edit",
            ),
            (
                "/control-center/users/550e8400-e29b-41d4-a716-446655440000/edit",  # noqa
                "Users — Edit",
            ),
        ]
        for url, expected in test_cases:
            with self.subTest(url=url):
                self.assertEqual(get_page_context(url), expected)

    def test_chatbot_get_page_context_fallback(self):
        """Assert fallback context for unrecognised, empty, or root URLs."""
        fallbacks = ["", None, "/"]
        for url in fallbacks:
            with self.subTest(url=url):
                self.assertEqual(get_page_context(url), "General Platform")

    def test_chatbot_serializer_validation(self):
        """Assert request serializer validates required message field."""
        # Valid payload
        valid_data = {
            "message": "How do I add a question?",
            "page_url": "/form-builder/1/edit",
            "thread_id": "thread_123",
        }
        serializer = ChatRequestSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

        # Missing message
        missing_data = {"page_url": "/data"}
        serializer = ChatRequestSerializer(data=missing_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("message", serializer.errors)

        # Blank message
        blank_data = {"message": "", "page_url": "/data"}
        serializer = ChatRequestSerializer(data=blank_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("message", serializer.errors)

    def test_chatbot_requires_auth(self):
        """Assert unauthenticated request returns 401 Unauthorized."""
        response = self.client.post(
            "/api/v1/chatbot/message",
            {"message": "Hello?"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_chatbot_authenticated_flow(self):
        """Assert authenticated request succeeds with valid 200 response."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/chatbot/message",
            {
                "message": "How do I create a form?",
                "page_url": "/control-center/form-builder",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertIn("thread_id", data)

        # Validate response matches serializer contract
        resp_serializer = ChatResponseSerializer(data=data)
        self.assertTrue(resp_serializer.is_valid())
