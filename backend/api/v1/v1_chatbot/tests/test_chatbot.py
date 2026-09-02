from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from api.v1.v1_chatbot.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
)
from api.v1.v1_chatbot.utils import (
    clean_citation_sources,
    get_page_context,
)
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

    def test_clean_citation_sources(self):
        """Assert OpenAI citation annotations are cleanly removed."""
        sample_text = (
            "You can approve or decline datasets and provide feedback【4:0†source】.\n"  # noqa
            "Edit according to feedback【4:1†source】【4:2†source】.\n"
            "View notifications【4:6†source】."
        )
        expected = (
            "You can approve or decline datasets and provide feedback.\n"
            "Edit according to feedback.\n"
            "View notifications."
        )
        self.assertEqual(clean_citation_sources(sample_text), expected)
        self.assertEqual(clean_citation_sources(""), "")
        self.assertEqual(clean_citation_sources(None), "")

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_VECTOR_STORE_ID="vs_test_123",
    )
    def test_chatbot_temperature_zero_enforced(self):
        """Assert temperature=0.0 is enforced on OpenAI Responses API calls."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "output_text"
        mock_content.text = "Grounded response about Akvo MIS."
        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.content = [mock_content]
        mock_response.output = [mock_output]
        mock_response.id = "resp_12345"

        mock_client.responses.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            self.client.force_authenticate(user=self.user)
            response = self.client.post(
                "/api/v1/chatbot/message",
                {
                    "message": "Can I use Kobo form builder here?",
                    "page_url": "/control-center/form-builder",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 200)

            # Assert responses.create was called with temperature=0.0
            mock_client.responses.create.assert_called_once()
            _, kwargs = mock_client.responses.create.call_args
            self.assertEqual(kwargs.get("temperature"), 0.0)
            self.assertEqual(kwargs.get("model"), "gpt-4o-mini")

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_VECTOR_STORE_ID="vs_test_123",
    )
    def test_chatbot_multi_tenant_consistency(self):
        """Assert multi-tenant requests produce consistent responses."""
        from unittest.mock import MagicMock, patch
        from api.v1.v1_users.models import Tenant

        # Create two distinct tenants
        tenant_a, _ = Tenant.objects.get_or_create(subdomain="tenant-a")
        tenant_b, _ = Tenant.objects.get_or_create(subdomain="tenant-b")

        user_a = SystemUser.objects.create_user(
            email="user_a@tenant-a.org",
            first_name="User",
            last_name="A",
            password="testpassword123",
            tenant=tenant_a,
        )
        user_b = SystemUser.objects.create_user(
            email="user_b@tenant-b.org",
            first_name="User",
            last_name="B",
            password="testpassword123",
            tenant=tenant_b,
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "output_text"
        mock_content.text = (
            "You cannot directly embed Kobo, but you can import an "
            "XLSForm (.xlsx) via Control Centre > Form Builder > Import Form."
        )
        mock_output = MagicMock()
        mock_output.type = "message"
        mock_output.content = [mock_content]
        mock_response.output = [mock_output]
        mock_response.id = "resp_fixed"
        mock_client.responses.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            client_a = APIClient()
            client_a.force_authenticate(user=user_a)
            res_a = client_a.post(
                "/api/v1/chatbot/message",
                {
                    "message": "the form builder on kobo can be used here?",
                    "page_url": "/control-center",
                },
                format="json",
                HTTP_HOST="tenant-a.localhost",
            )
            self.assertEqual(res_a.status_code, 200)

            client_b = APIClient()
            client_b.force_authenticate(user=user_b)
            res_b = client_b.post(
                "/api/v1/chatbot/message",
                {
                    "message": "the form builder on kobo can be used here?",
                    "page_url": "/control-center",
                },
                format="json",
                HTTP_HOST="tenant-b.localhost",
            )
            self.assertEqual(res_b.status_code, 200)

            # Assert identical output across tenants
            self.assertEqual(
                res_a.json()["response"],
                res_b.json()["response"],
            )
            self.assertIn("XLSForm", res_a.json()["response"])
            self.assertIn("Import Form", res_a.json()["response"])
