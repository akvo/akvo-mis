# =========================================================
# Backend AI Recommendation Engine & Service (VIZ-AI-002)
# =========================================================
# Stateless orchestration service combining OpenAI structured output
# with deterministic rule-based heuristics fallback.

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db.models import Count, Q

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import FormTypes, QuestionTypes
from api.v1.v1_forms.models import Forms, Questions
from api.v1.v1_visualization.ai.ai_heuristics import (
    generate_starter_heuristics,
    generate_widget_heuristics,
)
from api.v1.v1_visualization.ai.ai_prompts import (
    STARTER_DASHBOARD_JSON_SCHEMA,
    WIDGET_SUGGESTION_JSON_SCHEMA,
    build_starter_dashboard_prompt,
    build_widget_suggestion_prompt,
)
from api.v1.v1_visualization.constants import (
    SUPPORTED_QUESTION_TYPES,
    VALID_REPEAT_AGG,
    WidgetTypes,
)
from api.v1.v1_visualization.models import Dashboard

logger = logging.getLogger(__name__)

# Non-visualized binary / asset question types
NON_VISUALIZED_TYPES = {
    QuestionTypes.image,
    QuestionTypes.attachment,
    QuestionTypes.signature,
    QuestionTypes.text,  # long free-text notes
}

# Thematic questions supported on Map widgets (coloring/sizing)
MAP_THEMATIC_QUESTION_TYPES = {
    QuestionTypes.option,
    QuestionTypes.multiple_option,
    QuestionTypes.number,
    QuestionTypes.autofield,
}

# Numeric question types supported on Scatter question_y
NUMERIC_QUESTION_TYPES = {
    QuestionTypes.number,
    QuestionTypes.autofield,
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
            "form_questions__question_group",
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
            "form_questions__question_group",
        ).order_by("id")
    )

    sources_map: Dict[Any, Any] = {}

    all_family_forms = [root_form] + monitoring_forms

    # Fast indexed aggregates to check actual data presence
    form_submission_counts = dict(
        FormData.objects.filter(
            form__in=all_family_forms, deleted_at__isnull=True
        )
        .values("form_id")
        .annotate(c=Count("id"))
        .values_list("form_id", "c")
    )

    question_answer_counts = dict(
        Answers.objects.filter(
            question__form__in=all_family_forms,
            data__deleted_at__isnull=True,
        )
        .values("question_id")
        .annotate(c=Count("id"))
        .values_list("question_id", "c")
    )

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

            type_name = QuestionTypes.FieldStr.get(q.type, "unknown").lower()
            group_name = q.question_group.name if q.question_group else None
            ans_count = question_answer_counts.get(q.id, 0)
            q_info = {
                "id": q.id,
                "label": q.label or q.name,
                "type": q.type,
                "type_name": type_name,
                "group_name": group_name,
                "option_count": opt_count,
                "answer_count": ans_count,
                "has_data": ans_count > 0,
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
                "group_name": group_name,
                "option_count": opt_count,
                "answer_count": ans_count,
                "has_data": ans_count > 0,
            }

        sources_map[form_obj.id] = q_map
        return q_list

    root_questions = _extract_questions(root_form)

    mon_list = []
    for m_form in monitoring_forms:
        m_qs = _extract_questions(m_form)
        sub_count = form_submission_counts.get(m_form.id, 0)
        mon_list.append(
            {
                "id": m_form.id,
                "name": m_form.name,
                "submission_count": sub_count,
                "has_data": sub_count > 0,
                "questions": m_qs,
            }
        )

    root_sub_count = form_submission_counts.get(root_form.id, 0)
    total_family_submissions = sum(form_submission_counts.values())
    metadata = {
        "root_form": {
            "id": root_form.id,
            "name": root_form.name,
            "submission_count": root_sub_count,
            "has_data": root_sub_count > 0,
            "questions": root_questions,
        },
        "monitoring_forms": mon_list,
        "has_monitoring": bool(mon_list),
        "total_submissions": total_family_submissions,
    }

    sources_map["_form_submissions"] = form_submission_counts
    sources_map["_question_answers"] = question_answer_counts
    sources_map["_total_submissions"] = total_family_submissions

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
        q for q in form_qs.values() if q.get("type") == QuestionTypes.date
    ]
    date_q_id = None
    if date_qs:
        date_q = date_qs[0]
        date_q_id = date_q["id"]
        columns.append(
            {
                "key": f"q_{date_q_id}",
                "source": "latest_date",
                "question": date_q_id,
                "label": "Last submission",
            }
        )

    indicator_types = MAP_THEMATIC_QUESTION_TYPES
    m_indicators = [
        q
        for q in form_qs.values()
        if q.get("type") in indicator_types and q.get("id") != date_q_id
    ]
    for q in m_indicators[:3]:
        columns.append(
            {
                "key": f"q_{q['id']}",
                "source": "answer",
                "question": q["id"],
                "label": q.get("label") or f"Question {q['id']}",
            }
        )

    if len(m_indicators) < 2 and root_form_id and root_form_id in sources_map:
        root_qs = sources_map.get(root_form_id, {})
        r_indicators = [
            q for q in root_qs.values() if q.get("type") in indicator_types
        ]
        for rq in r_indicators[:2]:
            columns.append(
                {
                    "key": f"q_{rq['id']}",
                    "source": "parent_answer",
                    "question": rq["id"],
                    "label": rq.get("label") or f"Question {rq['id']}",
                }
            )

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
        WidgetTypes.scatter: "scatter",
        "scatter": "scatter",
        "scatter_plot": "scatter",
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
            valid_types = SUPPORTED_QUESTION_TYPES | {QuestionTypes.geo}
            if q_type not in valid_types:
                continue

        # Data availability guard: Drop chart/table widgets targeting forms
        # with 0 submissions or questions with 0 answers (prevents empty
        # "No data available" widgets) when the family has active submissions
        total_family_sub = sources_map.get("_total_submissions", 0)
        if total_family_sub > 0:
            form_sub_counts = sources_map.get("_form_submissions")
            if form_sub_counts is not None and form_id in form_sub_counts:
                if form_sub_counts[form_id] == 0:
                    is_headline = (
                        w_type == "kpi"
                        and q_id is None
                        and form_id == root_form_id
                    )
                    if not is_headline:
                        continue

            question_ans_counts = sources_map.get("_question_answers")
            if question_ans_counts is not None:
                if q_id and question_ans_counts.get(q_id, 0) == 0:
                    continue
        else:
            question_ans_counts = None

        config = item.get("config") or {}
        if not isinstance(config, dict):
            config = {}

        # Validate repeat_agg if provided
        repeat_agg = config.get("repeat_agg")
        if repeat_agg and repeat_agg not in VALID_REPEAT_AGG:
            config["repeat_agg"] = "sum"

        # Categorical option guard: requires option_count > 0
        if q_id and (
            w_type == "pie"
            or (w_type == "bar" and config.get("group_by") == "option")
        ):
            q_info = sources_map.get(form_id or 0, {}).get(q_id or 0, {})
            if q_info.get("type") in (
                QuestionTypes.option,
                QuestionTypes.multiple_option,
            ):
                if q_info.get("option_count") == 0:
                    continue
            elif config.get("group_by") == "option":
                # A non-option question cannot be grouped by option
                continue

        # Scatter widget question_y sanitization
        if w_type == "scatter":
            qy = config.get("question_y")
            if qy:
                target_form_qs = sources_map.get(form_id or 0, {})
                if qy not in target_form_qs:
                    config["question_y"] = None
                else:
                    qy_type = target_form_qs[qy].get("type")
                    if qy_type not in NUMERIC_QUESTION_TYPES:
                        config["question_y"] = None
                    elif (
                        question_ans_counts is not None
                        and question_ans_counts.get(qy, 0) == 0
                    ):
                        config["question_y"] = None

        # Line widget date_question_id sanitization
        if w_type == "line":
            target_form_qs = sources_map.get(form_id or 0, {})
            date_qid = config.get("date_question_id")
            if date_qid and (
                date_qid not in target_form_qs
                or target_form_qs[date_qid].get("type") != QuestionTypes.date
            ):
                date_qid = None
            if not date_qid:
                is_date = (
                    target_form_qs.get(q_id, {}).get("type")
                    == QuestionTypes.date
                )
                if q_id and is_date:
                    date_qid = q_id
                    q_id = None
                else:
                    for cand_qid, cand_info in target_form_qs.items():
                        if cand_info.get("type") == QuestionTypes.date:
                            date_qid = cand_qid
                            break
            if not date_qid:
                continue
            if (
                question_ans_counts is not None
                and question_ans_counts.get(date_qid, 0) == 0
            ):
                continue
            config["date_question_id"] = date_qid

        # Disallow cross-monitoring stack configurations
        if config.get("stack_form") and config.get("stack_form") != form_id:
            config["stack_form"] = None
            config["stack_question"] = None
            config.pop("stack_by", None)
        stack_q = config.get("stack_question")
        if stack_q and stack_q not in sources_map.get(form_id or 0, {}):
            config["stack_question"] = None
            config.pop("stack_by", None)

        # Map widget question sanitization:
        # In Akvo MIS, registration forms provide coordinates automatically.
        # A map widget's `question` field is ONLY for optional thematic
        # coloring (option/number) or None (point mode). It must NEVER be a
        # `geo` question ID.
        if w_type == "map":
            if q_id:
                target_form_qs = sources_map.get(form_id or 0, {})
                q_info = target_form_qs.get(q_id, {})
                q_type = q_info.get("type")
                if q_type not in MAP_THEMATIC_QUESTION_TYPES:
                    q_id = None
            if not q_id:
                config["map_mode"] = "point"

        # Table widget columns sanitization & auto-generation
        if w_type == "table":
            if root_form_id and form_id == root_form_id:
                continue
            cols = config.get("columns")
            valid_cols = []
            seen_keys = set()
            if isinstance(cols, list):
                for col in cols:
                    if not isinstance(col, dict):
                        continue
                    src = col.get("source")
                    if src not in (
                        "parent_name",
                        "administration",
                        "answer",
                        "parent_answer",
                        "latest_date",
                    ):
                        continue
                    col_qid = col.get("question") or col.get("question_id")
                    if col_qid is not None:
                        try:
                            col_qid = int(col_qid)
                        except (TypeError, ValueError):
                            col_qid = None

                    if src == "answer":
                        # Strictly must belong to widget's form
                        if not col_qid or col_qid not in sources_map.get(
                            form_id or 0, {}
                        ):
                            continue
                    elif src == "parent_answer":
                        # Strictly must belong to root_form
                        if not col_qid or col_qid not in sources_map.get(
                            root_form_id or 0, {}
                        ):
                            continue
                    elif src == "latest_date":
                        # If question specified, must belong to widget's form
                        if col_qid and col_qid not in sources_map.get(
                            form_id or 0, {}
                        ):
                            continue
                    elif src in ("parent_name", "administration"):
                        col_qid = None

                    raw_key = col.get("key") or f"col_{len(valid_cols)}"
                    col_key = str(raw_key).strip()
                    if not col_key:
                        col_key = f"col_{len(valid_cols)}"
                    if col_key in seen_keys:
                        col_key = f"{col_key}_{len(valid_cols)}"
                    seen_keys.add(col_key)

                    valid_cols.append(
                        {
                            "key": col_key,
                            "source": src,
                            "question": col_qid,
                            "label": (
                                col.get("label") or col_key or "Column"
                            ),
                        }
                    )

            if not valid_cols:
                valid_cols = _build_default_table_columns(
                    form_id=form_id,
                    root_form_id=root_form_id,
                    sources_map=sources_map,
                )
            config["columns"] = valid_cols
            if not isinstance(config.get("criteria"), list):
                config["criteria"] = []
            config.pop("measure", None)

        # Auto-populate axis labels from question labels for chart readability
        target_qs = sources_map.get(form_id or 0, {})
        q_info = target_qs.get(q_id or 0, {})
        q_label = q_info.get("label") or q_info.get("name")
        if w_type == "bar":
            is_horiz = config.get("orientation") == "horizontal"
            if is_horiz:
                if not config.get("y_axis_label") and q_label:
                    config["y_axis_label"] = q_label
            else:
                if not config.get("x_axis_label") and q_label:
                    config["x_axis_label"] = q_label
        elif w_type == "line":
            date_qid = config.get("date_question_id")
            date_label = (
                target_qs.get(date_qid, {}).get("label") if date_qid else None
            )
            if not config.get("x_axis_label") and date_label:
                config["x_axis_label"] = date_label
            if not config.get("y_axis_label") and q_label:
                config["y_axis_label"] = q_label
        elif w_type == "scatter":
            if not config.get("x_axis_label") and q_label:
                config["x_axis_label"] = q_label
            qy = config.get("question_y")
            qy_label = target_qs.get(qy, {}).get("label") if qy else None
            if not config.get("y_axis_label") and qy_label:
                config["y_axis_label"] = qy_label

        # Ensure measure integrity across monitoring and registration forms
        if w_type == "table":
            config.pop("measure", None)
        elif root_form_id and form_id and form_id != root_form_id:
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
        rationale = str(item.get("rationale") or "Recommended metric.").strip()

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


def _verify_widgets_with_engine(
    widgets: List[Dict],
    root_form_id: Optional[int],
    user,
) -> List[Dict]:
    """Defense-in-depth gate validating widgets against _validate_widget.

    Ensures 100% parity with POST /manage/dashboards payload validation.
    """
    if not widgets or not root_form_id or not user:
        return widgets

    try:
        from api.v1.v1_visualization.dashboard_functions import (
            _validate_widget,
        )

        user_forms = Forms.objects.for_user(user)
        root_form = user_forms.filter(pk=root_form_id).first()
        if not root_form:
            return widgets

        family_forms = user_forms.filter(
            Q(pk=root_form_id) | Q(parent_id=root_form_id)
        )
        user_questions = Questions.objects.for_user(user).filter(
            form__in=family_forms
        )

        verified = []
        for idx, w in enumerate(widgets):
            err = _validate_widget(
                w, idx, root_form, family_forms, user_questions, set()
            )
            if not err:
                verified.append(w)
            else:
                logger.warning(
                    "AI candidate widget dropped by _validate_widget: %s (%s)",
                    w.get("title"),
                    err,
                )
        return normalize_grid_layout(verified)
    except Exception as exc:
        logger.warning(
            "Could not run _validate_widget parity gate: %s",
            exc,
        )
        return widgets


def calculate_ai_timeout(
    family_metadata: Optional[dict] = None,
) -> Any:
    """Compute adaptive HTTP timeout based on question count and form size.

    - Base connect: 3.0s, base read: 6.0s
    - Read timeout scales by 0.1s per question, bounded between 6.0s and 15.0s
    - Total timeout = read_timeout + 3.0s (connect)
    """
    import httpx

    total_questions = 0
    if family_metadata and isinstance(family_metadata, dict):
        root_form = family_metadata.get("root_form") or {}
        root_qs = root_form.get("questions") or []
        total_questions += len(root_qs)

        mon_forms = family_metadata.get("monitoring_forms") or []
        for m in mon_forms:
            if isinstance(m, dict):
                total_questions += len(m.get("questions") or [])

    read_timeout = max(6.0, min(15.0, 6.0 + total_questions * 0.1))
    total_timeout = read_timeout + 3.0
    return httpx.Timeout(total_timeout, connect=3.0, read=read_timeout)


class AISuggestionService:
    """Core recommendation orchestrator for Akvo MIS dashboards."""

    @classmethod
    def _call_openai(
        cls,
        messages: list,
        schema: dict,
        timeout: Optional[Any] = None,
    ) -> Optional[dict]:
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

            default_timeout = httpx.Timeout(10.0, connect=3.0, read=7.0)
            call_timeout = timeout or default_timeout
            client = OpenAI(api_key=api_key, timeout=call_timeout)

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

        # Attempt OpenAI generation with adaptive timeout based on form size
        messages = build_starter_dashboard_prompt(metadata, user_intent)
        call_timeout = calculate_ai_timeout(metadata)
        openai_result = cls._call_openai(
            messages, STARTER_DASHBOARD_JSON_SCHEMA, timeout=call_timeout
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
            valid_widgets = _verify_widgets_with_engine(
                valid_widgets, root_form_id, user
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
        valid_widgets = _verify_widgets_with_engine(
            valid_widgets, root_form_id, user
        )
        heuristic_res["widgets"] = valid_widgets
        heuristic_res["ai_available"] = False
        heuristic_res["provider"] = "heuristics"
        return heuristic_res

    @classmethod
    def _deduplicate_suggestions(
        cls,
        suggestions: List[Dict],
        existing_widgets: List[Dict],
    ) -> List[Dict]:
        """Post-filter suggestions to ensure no duplicate questions or maps."""
        seen_questions = set()
        has_map = False

        for w in existing_widgets:
            w_type = w.get("type")
            if w_type in ("map", WidgetTypes.map):
                has_map = True
            q = w.get("question")
            if q:
                seen_questions.add(q)
            cfg = w.get("config")
            if isinstance(cfg, dict):
                if cfg.get("question_y"):
                    seen_questions.add(cfg["question_y"])
                if cfg.get("date_question_id"):
                    seen_questions.add(cfg["date_question_id"])

        deduped = []
        for s in suggestions:
            stype = s.get("type")
            sq = s.get("question")
            if stype in ("map", WidgetTypes.map):
                if has_map:
                    continue
                has_map = True

            if sq and sq in seen_questions:
                continue

            cfg = s.get("config")
            if isinstance(cfg, dict):
                qy = cfg.get("question_y")
                if qy and qy in seen_questions:
                    continue

            deduped.append(s)
            if sq:
                seen_questions.add(sq)

        return deduped

    @classmethod
    def suggest_widgets(
        cls,
        dashboard_id: int,
        user,
        existing_widget_types: Optional[List[str]] = None,
        prompt_hint: Optional[str] = None,
        existing_widgets: Optional[List[Dict]] = None,
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

        # Combine database-persisted widgets with client-supplied widgets
        persisted = list(
            dashboard.widgets.values(
                "id", "type", "form_id", "question_id", "config", "title"
            )
        )
        all_existing: List[Dict] = []
        for pw in persisted:
            all_existing.append(
                {
                    "type": pw["type"],
                    "form": pw["form_id"],
                    "question": pw["question_id"],
                    "config": pw["config"] or {},
                    "title": pw.get("title") or "",
                }
            )
        if existing_widgets and isinstance(existing_widgets, list):
            for ew in existing_widgets:
                if isinstance(ew, dict):
                    all_existing.append(ew)

        merged_types = list(
            set(
                (existing_widget_types or [])
                + [w.get("type") for w in all_existing if w.get("type")]
            )
        )

        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            return {
                "ai_available": False,
                "provider": "none",
                "suggestions": [],
            }

        if not ai_circuit_breaker.is_open:
            messages = build_widget_suggestion_prompt(
                metadata,
                existing_widget_types=merged_types,
                prompt_hint=prompt_hint,
                existing_widgets=all_existing,
            )
            call_timeout = calculate_ai_timeout(metadata)
            openai_result = cls._call_openai(
                messages,
                WIDGET_SUGGESTION_JSON_SCHEMA,
                timeout=call_timeout,
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
                valid_suggestions = _verify_widgets_with_engine(
                    valid_suggestions, root_form_id, user
                )
                deduped = cls._deduplicate_suggestions(
                    valid_suggestions, all_existing
                )
                return {
                    "ai_available": True,
                    "provider": "openai",
                    "suggestions": deduped,
                }

        # Fall back to deterministic heuristics
        heuristic_res = generate_widget_heuristics(
            metadata,
            existing_widget_types=merged_types,
            prompt_hint=prompt_hint,
            existing_widgets=all_existing,
        )
        valid_suggestions = validate_and_sanitize_widgets(
            heuristic_res.get("suggestions", []),
            sources_map,
            has_monitoring,
            root_form_id,
        )
        valid_suggestions = _verify_widgets_with_engine(
            valid_suggestions, root_form_id, user
        )
        deduped = cls._deduplicate_suggestions(valid_suggestions, all_existing)
        return {
            "ai_available": True,
            "provider": "heuristics",
            "suggestions": deduped,
        }
