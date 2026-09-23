import json
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import (
    Forms,
    QuestionGroup,
    QuestionOptions,
    Questions,
)
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_visualization.ai_heuristics import (
    generate_starter_heuristics,
    generate_widget_heuristics,
)
from api.v1.v1_visualization.ai_prompts import (
    MAX_USER_INTENT_LENGTH,
    build_starter_dashboard_prompt,
    sanitize_user_input,
)
from api.v1.v1_visualization.ai_service import (
    AISuggestionService,
    CircuitBreaker,
    ai_circuit_breaker,
    extract_family_metadata,
    normalize_grid_layout,
    validate_and_sanitize_widgets,
)
from api.v1.v1_visualization.constants import DashboardKind, WidgetTypes
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False, OPENAI_API_KEY=None)
class AIVisualizationTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        ai_circuit_breaker.failure_count = 0
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="ai_viz_author@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        token = RefreshToken.for_user(self.user).access_token
        self.header = {
            "HTTP_AUTHORIZATION": f"Bearer {token}"
        }
        self.root = Forms.objects.get(pk=6001)
        self.monitoring = Forms.objects.get(pk=6002)

        self.dashboard = Dashboard.objects.create(
            name="Water Facilities",
            slug="water-facilities",
            root_form=self.root,
            created_by=self.user,
        )

        self.suggest_dashboard_url = (
            "/api/v1/manage/dashboards/ai/suggest-dashboard"
        )
        self.suggest_widgets_url = (
            f"/api/v1/manage/dashboards/{self.dashboard.id}/ai/suggest-widgets"
        )

    # =========================================================
    # 1. Metadata Extraction & Privacy Tests
    # =========================================================

    def test_metadata_extraction_zero_pii(self):
        """Metadata extractor returns schema with no submission rows."""
        res = extract_family_metadata(self.root.id, self.user)
        self.assertIsNotNone(res)
        metadata, sources_map = res

        self.assertEqual(metadata["root_form"]["id"], self.root.id)
        self.assertTrue(metadata["has_monitoring"])
        self.assertTrue(len(metadata["monitoring_forms"]) >= 1)
        self.assertIn(self.root.id, sources_map)
        self.assertIn(self.monitoring.id, sources_map)

        # Check question fields
        q_item = metadata["root_form"]["questions"][0]
        self.assertIn("id", q_item)
        self.assertIn("label", q_item)
        self.assertIn("type", q_item)

    def test_metadata_extraction_not_found(self):
        """Non-existent form returns None."""
        res = extract_family_metadata(99999999, self.user)
        self.assertIsNone(res)

    # =========================================================
    # 2. Prompt Construction & Input Sanitization
    # =========================================================

    def test_input_sanitization(self):
        """Control characters stripped, HTML escaped, and length capped."""
        malicious = "Hello <script>alert(1)</script>\x00\x08" + ("A" * 300)
        clean = sanitize_user_input(malicious)
        self.assertNotIn("<script>", clean)
        self.assertNotIn("\x00", clean)
        self.assertLessEqual(len(clean), MAX_USER_INTENT_LENGTH)
        self.assertTrue(clean.startswith("Hello &lt;script&gt;"))

    def test_prompt_builder(self):
        """Prompt formats user intent in structural XML tags."""
        meta = {"root_form": {"id": 1, "name": "Test", "questions": []}}
        messages = build_starter_dashboard_prompt(meta, "Water supply focus")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn(
            "<user_intent>Water supply focus</user_intent>",
            messages[1]["content"],
        )

    # =========================================================
    # 3. Deterministic Heuristics Tests
    # =========================================================

    def test_starter_heuristics_generation(self):
        """Heuristic dashboard generates widgets with 24-col grid."""
        metadata, sources_map = extract_family_metadata(
            self.root.id, self.user
        )
        result = generate_starter_heuristics(metadata, "General Overview")
        self.assertIn("suggested_name", result)
        self.assertIn("widgets", result)
        widgets = result["widgets"]
        self.assertTrue(len(widgets) >= 3)

        widget_types = [w["type"] for w in widgets]
        self.assertIn("kpi", widget_types)

        # Check widget shape
        for w in widgets:
            self.assertIn("type", w)
            self.assertIn("title", w)
            self.assertIn("col_span", w)
            self.assertIn("rationale", w)
            self.assertIn("config", w)

    def test_registration_only_form_heuristics(self):
        """Registration form has no table and null measure."""
        standalone_form = Forms.objects.create(
            name="Standalone Facility Form",
            type=FormTypes.registration,
            status=FormStatus.published,
        )
        group = QuestionGroup.objects.create(
            form=standalone_form, name="Group 1", order=1
        )
        opt_q = Questions.objects.create(
            form=standalone_form,
            name="Facility Type",
            type=QuestionTypes.option,
            question_group=group,
            order=1,
        )
        QuestionOptions.objects.create(
            question=opt_q, label="Clinic", value="clinic", order=1
        )

        metadata, sources_map = extract_family_metadata(
            standalone_form.id, self.user
        )
        self.assertFalse(metadata["has_monitoring"])

        result = generate_starter_heuristics(metadata)
        widgets = result["widgets"]

        for w in widgets:
            self.assertNotEqual(w["type"], "table")
            self.assertIsNone(w.get("config", {}).get("measure"))

    def test_widget_heuristics_generation(self):
        """Contextual suggestions prioritize unvisualized questions."""
        metadata, sources_map = extract_family_metadata(
            self.root.id, self.user
        )
        result = generate_widget_heuristics(
            metadata, existing_widget_types=[WidgetTypes.kpi]
        )
        self.assertIn("suggestions", result)
        suggestions = result["suggestions"]
        self.assertTrue(len(suggestions) >= 1)

    # =========================================================
    # 4. Referential Integrity & Grid Normalization Tests
    # =========================================================

    def test_referential_integrity_prunes_hallucinations(self):
        """Invalid question and form IDs are removed."""
        metadata, sources_map = extract_family_metadata(
            self.root.id, self.user
        )
        raw_widgets = [
            # Valid KPI
            {
                "type": WidgetTypes.kpi,
                "title": "Valid KPI",
                "col_span": 6,
                "form": self.root.id,
                "question": None,
                "config": {"value_type": "number"},
                "rationale": "Valid.",
            },
            # Hallucinated form
            {
                "type": WidgetTypes.pie,
                "title": "Hallucinated Form",
                "col_span": 8,
                "form": 99999999,
                "question": 101,
                "config": {},
                "rationale": "Invalid.",
            },
            # Hallucinated question
            {
                "type": WidgetTypes.bar,
                "title": "Hallucinated Question",
                "col_span": 8,
                "form": self.root.id,
                "question": 99999999,
                "config": {},
                "rationale": "Invalid.",
            },
        ]

        valid = validate_and_sanitize_widgets(
            raw_widgets, sources_map, has_monitoring=True
        )
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["title"], "Valid KPI")

    def test_24_column_grid_normalizer(self):
        """Uneven column spans are balanced to cleanly fit 24-col rows."""
        widgets = [
            {"col_span": 6, "title": "W1"},
            {"col_span": 6, "title": "W2"},
            {"col_span": 6, "title": "W3"},
            {"col_span": 12, "title": "W4"},
        ]
        normalized = normalize_grid_layout(widgets)
        # First row was 6+6+6=18, so W3 gets expanded by remainder (+6)
        self.assertEqual(normalized[2]["col_span"], 12)
        # Second row is 12, expanded to 24
        self.assertEqual(normalized[3]["col_span"], 24)

    # =========================================================
    # 5. Circuit Breaker Resilience Tests
    # =========================================================

    def test_circuit_breaker(self):
        """Trips after 3 failures and resets after cooldown or success."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.1)
        self.assertFalse(cb.is_open)

        cb.record_failure()
        cb.record_failure()
        self.assertFalse(cb.is_open)

        cb.record_failure()
        self.assertTrue(cb.is_open)

        cb.record_success()
        self.assertFalse(cb.is_open)

    # =========================================================
    # 6. Endpoints Integration Tests (HTTP POST)
    # =========================================================

    def test_suggest_dashboard_endpoint_success(self):
        """POST /manage/dashboards/ai/suggest-dashboard returns 200 OK."""
        payload = {
            "root_form": self.root.id,
            "user_intent": "Monitor water point functionality",
        }
        response = self.client.post(
            self.suggest_dashboard_url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("suggested_name", data)
        self.assertIn("description", data)
        self.assertIn("widgets", data)
        self.assertTrue(len(data["widgets"]) >= 3)

    def test_suggest_dashboard_endpoint_not_found(self):
        """POST with non-existent root_form returns 404 Not Found."""
        payload = {"root_form": 88888888}
        response = self.client.post(
            self.suggest_dashboard_url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_suggest_widgets_endpoint_success(self):
        """POST /manage/dashboards/<pk>/ai/suggest-widgets returns 200 OK."""
        payload = {
            "existing_widget_types": ["kpi"],
            "prompt_hint": "Suggest bar charts",
        }
        response = self.client.post(
            self.suggest_widgets_url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("suggestions", data)
        self.assertTrue(len(data["suggestions"]) >= 1)

    def test_suggest_widgets_embed_rejected(self):
        """Embedded dashboard cannot request widget suggestions."""
        embed_dash = Dashboard.objects.create(
            name="Embed Dash",
            slug="embed-dash",
            kind=DashboardKind.embed,
            embed_snippet="<iframe></iframe>",
            created_by=self.user,
        )
        url = f"/api/v1/manage/dashboards/{embed_dash.id}/ai/suggest-widgets"
        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suggest_dashboard_anonymous_forbidden(self):
        """Anonymous user cannot access suggestion endpoints."""
        response = self.client.post(
            self.suggest_dashboard_url,
            data=json.dumps({"root_form": self.root.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =========================================================
    # 7. OpenAI Mock Structured Output Test
    # =========================================================

    @override_settings(OPENAI_API_KEY="sk-test-mock-key")
    def test_openai_structured_output_success(self):
        """OpenAI structured JSON response is parsed and sanitized."""
        root_opt_q = self.root.form_questions.filter(
            type=QuestionTypes.option
        ).first()
        monitoring_date_q = self.monitoring.form_questions.filter(
            type=QuestionTypes.date
        ).first()

        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(
            {
                "suggested_name": "AI AI AI Water Overview",
                "description": "Smart overview generated by OpenAI.",
                "widgets": [
                    {
                        "type": "kpi",
                        "title": "Site Count",
                        "col_span": 6,
                        "color": None,
                        "form": self.root.id,
                        "question": None,
                        "config": {"value_type": "number"},
                        "rationale": "High-level count.",
                    },
                    {
                        "type": "pie",
                        "title": "Status Breakdown",
                        "col_span": 8,
                        "color": None,
                        "form": self.root.id,
                        "question": root_opt_q.id if root_opt_q else None,
                        "config": {
                            "group_by": "option",
                            "variant": "doughnut",
                            "color_scheme": "categorical",
                        },
                        "rationale": "Status proportion.",
                    },
                    {
                        "type": "line",
                        "title": "Activity Over Time",
                        "col_span": 12,
                        "color": None,
                        "form": self.monitoring.id,
                        "question": (
                            monitoring_date_q.id if monitoring_date_q else None
                        ),
                        "config": {
                            "group_by": "month",
                            "date_question_id": (
                                monitoring_date_q.id
                                if monitoring_date_q
                                else None
                            ),
                            "color_scheme": "categorical",
                        },
                        "rationale": "Monthly monitoring trend.",
                    },
                ],
            }
        )
        mock_response.choices = [MagicMock(message=mock_message)]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            res = AISuggestionService.suggest_dashboard(
                self.root.id, self.user
            )
            self.assertIsNotNone(res)
            self.assertEqual(res["suggested_name"], "AI AI AI Water Overview")
            self.assertEqual(len(res["widgets"]), 3)
