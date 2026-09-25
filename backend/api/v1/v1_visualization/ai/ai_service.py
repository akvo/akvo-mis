# =========================================================
# Backend AI Recommendation Engine & Service (VIZ-AI-002)
# =========================================================
# Stateless orchestration service combining OpenAI structured output
# with deterministic rule-based heuristics fallback.

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

from django.conf import settings

from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_visualization.ai.ai_heuristics import (
    generate_starter_heuristics,
)
from api.v1.v1_visualization.ai.ai_prompts import (
    STARTER_DASHBOARD_JSON_SCHEMA,
    WIDGET_SUGGESTION_JSON_SCHEMA,
    build_starter_dashboard_prompt,
    build_widget_suggestion_prompt,
)
from api.v1.v1_visualization.constants import (
    SUPPORTED_QUESTION_TYPES,
    WidgetTypes,
)
from api.v1.v1_visualization.models import Dashboard

logger = logging.getLogger(__name__)

# Valid aggregation methods for repeated questions
VALID_REPEAT_AGG = {"sum", "average", "count", "min", "max"}

# Non-visualized binary / asset question types
NON_VISUALIZED_TYPES = {
    QuestionTypes.image,
    QuestionTypes.attachment,
    QuestionTypes.signature,
    QuestionTypes.text,  # long free-text notes
}

MAX_OPTIONS_IN_PROMPT = 15


class CircuitBreaker:
    """In-memory circuit breaker protecting backend worker threads.

    Trips after consecutive failures (default: 3) and remains OPEN for
    cooldown_seconds (default: 60s), during which requests immediately
    bypass the external network and route to heuristics.
    """

    def __init__(
        self, failure_threshold: int = 3, cooldown_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.last_failure_time = 0.0

    @property
    def is_open(self) -> bool:
        if self.failure_count >= self.failure_threshold:
            if (time.time() - self.last_failure_time) < self.cooldown_seconds:
                return True
            # Cooldown expired, enter half-open
            self.failure_count = 0
        return False

    def record_success(self):
        self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()


# Global module-level circuit breaker instance
ai_circuit_breaker = CircuitBreaker()


def extract_family_metadata(
    root_form_id: int,
    user,
    monitoring_form_ids: Optional[List[int]] = None,
) -> Optional[Tuple[Dict, Dict]]:
    """Extract compact structural metadata from the active form family.

    Returns a tuple of:
    - metadata dict (for prompt and heuristics)
    - sources_map dict { form_id: { question_id: question_dict } }

    Uses prefetch_related to eliminate N+1 queries. Zero submission rows
    or GPS answer points are accessed.
    """
    root_form = (
        Forms.objects.for_user(user)
        .filter(id=root_form_id, type=FormTypes.registration)
        .prefetch_related(
            "form_questions__options",
        )
        .first()
    )
    if not root_form:
        return None

    # Fetch child monitoring forms
    monitoring_qs = Forms.objects.for_user(user).filter(
        parent=root_form, type=FormTypes.monitoring
    )
    if monitoring_form_ids:
        monitoring_qs = monitoring_qs.filter(id__in=monitoring_form_ids)

    monitoring_forms = list(
        monitoring_qs.prefetch_related(
            "form_questions__options",
        ).order_by("id")
    )

    sources_map: Dict[int, Dict[int, Dict]] = {}

    def _extract_questions(form_obj) -> List[Dict]:
        q_map: Dict[int, Dict] = {}
        q_list: List[Dict] = []
        for q in form_obj.form_questions.all():
            if (
                q.type not in SUPPORTED_QUESTION_TYPES
                and q.type != QuestionTypes.geo
            ):
                continue

            opts = []
            if q.type in (
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ):
                all_opts = list(q.options.all().order_by("order", "id"))
                opts = [
                    {"label": opt.label, "value": opt.value}
                    for opt in all_opts[:MAX_OPTIONS_IN_PROMPT]
                ]
                opt_count = len(all_opts)
            else:
                opt_count = 0

            q_info = {
                "id": q.id,
                "label": q.label or q.name,
                "type": q.type,
                "option_count": opt_count,
            }
            if opts:
                q_info["options_sample"] = opts
                if opt_count > MAX_OPTIONS_IN_PROMPT:
                    q_info["truncated_options"] = True

            q_list.append(q_info)
            q_map[q.id] = {
                "id": q.id,
                "type": q.type,
                "label": q.label or q.name,
                "group_id": q.question_group_id,
            }

        sources_map[form_obj.id] = q_map
        return q_list

    root_questions = _extract_questions(root_form)

    mon_list = []
    for m_form in monitoring_forms:
        m_qs = _extract_questions(m_form)
        mon_list.append(
            {
                "id": m_form.id,
                "name": m_form.name,
                "questions": m_qs,
            }
        )

    metadata = {
        "root_form": {
            "id": root_form.id,
            "name": root_form.name,
            "questions": root_questions,
        },
        "monitoring_forms": mon_list,
        "has_monitoring": bool(mon_list),
    }

    return metadata, sources_map


def normalize_grid_layout(widgets: List[Dict]) -> List[Dict]:
    """Balance widget col_spans across standard 24-column grid rows."""
    if not widgets:
        return []

    for w in widgets:
        if w.get("type") in ("table", "map"):
            w["col_span"] = 24
        elif w.get("col_span") not in (6, 8, 12, 24):
            w["col_span"] = 12

    # Group widgets into rows
    current_row_sum = 0
    row: List[Dict] = []
    normalized: List[Dict] = []

    for w in widgets:
        span = w["col_span"]
        if current_row_sum + span <= 24:
            row.append(w)
            current_row_sum += span
            if current_row_sum == 24:
                normalized.extend(row)
                row = []
                current_row_sum = 0
        else:
            # Row wraps. If row left a small gap, expand items
            if row:
                remainder = 24 - current_row_sum
                if remainder > 0 and len(row) > 0:
                    row[-1]["col_span"] += remainder
                normalized.extend(row)
            row = [w]
            current_row_sum = span

    if row:
        remainder = 24 - current_row_sum
        if remainder > 0:
            row[-1]["col_span"] += remainder
        normalized.extend(row)

    return normalized


def _build_default_table_columns(
    form_id: Optional[int],
    root_form_id: Optional[int],
    sources_map: Dict[int, Dict[int, Dict]],
) -> List[Dict]:
    """Construct schema-valid default columns for a table widget."""
    columns = [
        {
            "key": "parent_name",
            "source": "parent_name",
            "label": "Datapoint name",
        },
        {
            "key": "administration",
            "source": "administration",
            "label": "Administration",
        },
    ]
    form_qs = sources_map.get(form_id or 0, {})
    # Check date question for latest_date
    date_qs = [
        q for q in form_qs.values()
        if q.get("type") in (QuestionTypes.date, "date")
    ]
    date_q_id = None
    if date_qs:
        date_q = date_qs[0]
        date_q_id = date_q["id"]
        columns.append({
            "key": f"q_{date_q_id}",
            "source": "latest_date",
            "question": date_q_id,
            "label": "Last submission",
        })

    indicator_types = {
        QuestionTypes.option,
        QuestionTypes.multiple_option,
        QuestionTypes.number,
        QuestionTypes.autofield,
        "option",
        "multiple_option",
        "number",
        "autofield",
    }
    m_indicators = [
        q for q in form_qs.values()
        if q.get("type") in indicator_types and q.get("id") != date_q_id
    ]
    for q in m_indicators[:3]:
        columns.append({
            "key": f"q_{q['id']}",
            "source": "answer",
            "question": q["id"],
            "label": q.get("label") or f"Question {q['id']}",
        })

    if len(m_indicators) < 2 and root_form_id and root_form_id in sources_map:
        root_qs = sources_map.get(root_form_id, {})
        r_indicators = [
            q for q in root_qs.values()
            if q.get("type") in indicator_types
        ]
        for rq in r_indicators[:2]:
            columns.append({
                "key": f"q_{rq['id']}",
                "source": "parent_answer",
                "question": rq["id"],
                "label": rq.get("label") or f"Question {rq['id']}",
            })

    return columns


def validate_and_sanitize_widgets(
    raw_widgets: List[Dict],
    sources_map: Dict[int, Dict[int, Dict]],
    has_monitoring: bool,
    root_form_id: Optional[int] = None,
) -> List[Dict]:
    """Sanitize and validate candidate widgets against sources_map.

    Drops hallucinations (non-existent forms/questions) and enforces
    domain rules (e.g. tables require monitoring forms and valid columns,
    charts set valid measure on monitoring forms).
    """
    valid_widgets: List[Dict] = []
    type_map = {
        WidgetTypes.kpi: "kpi",
        "kpi": "kpi",
        "kpi_card": "kpi",
        WidgetTypes.bar: "bar",
        "bar": "bar",
        "bar_chart": "bar",
        "stacked_bar_chart": "bar",
        "column_chart": "bar",
        WidgetTypes.line: "line",
        "line": "line",
        "line_chart": "line",
        WidgetTypes.pie: "pie",
        "pie": "pie",
        "pie_chart": "pie",
        "donut_chart": "pie",
        "doughnut_chart": "pie",
        WidgetTypes.table: "table",
        "table": "table",
        "table_view": "table",
        WidgetTypes.map: "map",
        "map": "map",
        "map_view": "map",
        "geo_map": "map",
    }

    for item in raw_widgets:
        if not isinstance(item, dict):
            continue
        raw_type = item.get("type")
        w_type = type_map.get(raw_type)
        if not w_type:
            continue

        form_id = item.get("form") or item.get("form_id")
        q_id = item.get("question") or item.get("question_id")

        # If form_id is not specified but question is present, locate form_id
        if not form_id and q_id:
            for fid, qmap in sources_map.items():
                if q_id in qmap:
                    form_id = fid
                    break

        # Table cannot exist on registration-only form
        if w_type == "table" and not has_monitoring:
            continue

        # Form referential integrity check
        if form_id and form_id not in sources_map:
            continue

        # Question referential integrity check
        if q_id:
            if not form_id:
                continue
            if q_id not in sources_map.get(form_id, {}):
                continue
            q_info = sources_map[form_id][q_id]
            q_type = q_info.get("type")
            valid_types = SUPPORTED_QUESTION_TYPES | {
                "number",
                "option",
                "multiple_option",
                "date",
                "autofield",
            }
            if q_type not in valid_types:
                continue

        config = item.get("config") or {}
        if not isinstance(config, dict):
            config = {}

        # Validate repeat_agg if provided
        repeat_agg = config.get("repeat_agg")
        if repeat_agg and repeat_agg not in VALID_REPEAT_AGG:
            config["repeat_agg"] = "sum"

        # Table widget columns sanitization & auto-generation
        if w_type == "table":
            cols = config.get("columns")
            valid_cols = []
            if isinstance(cols, list):
                for col in cols:
                    if not isinstance(col, dict):
                        continue
                    src = col.get("source")
                    if src not in (
                        "parent_name", "administration", "answer",
                        "parent_answer", "latest_date",
                    ):
                        continue
                    col_qid = col.get("question") or col.get("question_id")
                    if src in ("answer", "parent_answer", "latest_date"):
                        target_form = (
                            root_form_id if src == "parent_answer" else form_id
                        )
                        if not col_qid or col_qid not in sources_map.get(
                            target_form or form_id or 0, {}
                        ):
                            # Try other form in sources_map if misplaced
                            found_fid = None
                            for fid, qmap in sources_map.items():
                                if col_qid in qmap:
                                    found_fid = fid
                                    break
                            if not found_fid:
                                continue
                            col_qid = int(col_qid)
                    valid_cols.append({
                        "key": col.get("key") or f"col_{len(valid_cols)}",
                        "source": src,
                        "question": col_qid,
                        "label": (
                            col.get("label") or col.get("key") or "Column"
                        ),
                    })

            if not valid_cols:
                valid_cols = _build_default_table_columns(
                    form_id=form_id,
                    root_form_id=root_form_id,
                    sources_map=sources_map,
                )
            config["columns"] = valid_cols
            if not isinstance(config.get("criteria"), list):
                config["criteria"] = []

        # Ensure measure integrity across monitoring and registration forms
        if root_form_id and form_id and form_id != root_form_id:
            if not config.get("measure"):
                config["measure"] = (
                    "all_submissions" if w_type == "line" else "current_state"
                )
        elif root_form_id and form_id == root_form_id:
            config.pop("measure", None)

        col_span = item.get("col_span", 12)
        if w_type in ("table", "map"):
            col_span = 24
        elif col_span not in (6, 8, 12, 24):
            col_span = 12

        default_title = f"{w_type.capitalize()} Widget"
        title = str(item.get("title") or default_title).strip()[:255]
        rationale = str(
            item.get("rationale") or "Recommended metric."
        ).strip()

        valid_widgets.append(
            {
                "type": w_type,
                "title": title,
                "col_span": col_span,
                "color": item.get("color") or None,
                "form": form_id,
                "question": q_id,
                "config": config,
                "rationale": rationale,
            }
        )

    return normalize_grid_layout(valid_widgets)


class AISuggestionService:
    """Core recommendation orchestrator for Akvo MIS dashboards."""

    @classmethod
    def _call_openai(cls, messages: list, schema: dict) -> Optional[dict]:
        """Invoke OpenAI API with structured JSON and circuit breaker."""
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            return None

        if ai_circuit_breaker.is_open:
            logger.warning("AI circuit breaker is OPEN. Skipping OpenAI.")
            return None

        try:
            from openai import OpenAI
            import httpx

            # Strict granular timeouts: 2.0s connect, 4.0s read
            timeout = httpx.Timeout(5.0, connect=2.0, read=4.0)
            client = OpenAI(api_key=api_key, timeout=timeout)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format=schema,
                temperature=0.2,
                max_tokens=1500,
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                return None

            parsed = json.loads(raw_content)
            ai_circuit_breaker.record_success()
            return parsed

        except Exception as exc:
            ai_circuit_breaker.record_failure()
            logger.warning(
                "OpenAI suggestion failed (falling back to heuristics): %s",
                str(exc),
            )
            return None

    @classmethod
    def suggest_dashboard(
        cls,
        root_form_id: int,
        user,
        user_intent: Optional[str] = None,
        monitoring_form_ids: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        """Generate a complete starter dashboard layout for a root form."""
        meta_res = extract_family_metadata(
            root_form_id, user, monitoring_form_ids=monitoring_form_ids
        )
        if not meta_res:
            return None

        metadata, sources_map = meta_res
        has_monitoring = metadata.get("has_monitoring", False)

        # Attempt OpenAI generation
        messages = build_starter_dashboard_prompt(metadata, user_intent)
        openai_result = cls._call_openai(
            messages, STARTER_DASHBOARD_JSON_SCHEMA
        )

        if openai_result and isinstance(openai_result, dict):
            raw_widgets = (
                openai_result.get("widgets")
                or openai_result.get("suggestions")
                or openai_result.get("recommended_widgets")
                or []
            )
            valid_widgets = validate_and_sanitize_widgets(
                raw_widgets, sources_map, has_monitoring, root_form_id
            )
            if len(valid_widgets) >= 3:
                r_name = metadata["root_form"]["name"]
                s_name = str(
                    openai_result.get("suggested_name") or f"{r_name} Overview"
                )[:255]
                desc = str(
                    openai_result.get("description")
                    or f"Overview for {r_name}."
                )
                return {
                    "suggested_name": s_name,
                    "description": desc,
                    "widgets": valid_widgets,
                    "ai_available": True,
                    "provider": "openai",
                }

        # Fallback to deterministic heuristics
        heuristic_res = generate_starter_heuristics(metadata, user_intent)
        valid_widgets = validate_and_sanitize_widgets(
            heuristic_res["widgets"], sources_map, has_monitoring, root_form_id
        )
        heuristic_res["widgets"] = valid_widgets
        heuristic_res["ai_available"] = False
        heuristic_res["provider"] = "heuristics"
        return heuristic_res

    @classmethod
    def suggest_widgets(
        cls,
        dashboard_id: int,
        user,
        existing_widget_types: Optional[List[str]] = None,
        prompt_hint: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate contextual in-canvas widget suggestions."""
        dashboard = (
            Dashboard.objects.for_user(user)
            .filter(id=dashboard_id)
            .select_related("root_form")
            .first()
        )
        if not dashboard or not dashboard.root_form_id:
            return None

        meta_res = extract_family_metadata(dashboard.root_form_id, user)
        if not meta_res:
            return None

        metadata, sources_map = meta_res
        has_monitoring = metadata.get("has_monitoring", False)
        root_form_id = dashboard.root_form_id

        # Check if OpenAI API key is configured
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            return {
                "ai_available": False,
                "provider": "none",
                "suggestions": [],
            }

        # Attempt OpenAI generation
        messages = build_widget_suggestion_prompt(
            metadata, existing_widget_types, prompt_hint
        )
        openai_result = cls._call_openai(
            messages, WIDGET_SUGGESTION_JSON_SCHEMA
        )

        if openai_result and isinstance(openai_result, dict):
            raw_suggestions = (
                openai_result.get("suggestions")
                or openai_result.get("widgets")
                or openai_result.get("recommended_widgets")
                or []
            )
            valid_suggestions = validate_and_sanitize_widgets(
                raw_suggestions, sources_map, has_monitoring, root_form_id
            )
            if valid_suggestions:
                return {
                    "ai_available": True,
                    "provider": "openai",
                    "suggestions": valid_suggestions,
                }

        return {
            "ai_available": False,
            "provider": "none",
            "suggestions": [],
        }
