# =========================================================
# Deterministic AI Heuristics Engine (VIZ-AI-002)
# =========================================================
# Generates high-quality, schema-valid dashboard widgets without
# requiring an active OpenAI connection. Serves as the primary offline
# fallback and baseline rule engine for Akvo MIS.

from typing import Dict, List, Optional
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_visualization.constants import WidgetTypes


def _find_questions_by_type(
    questions: List[Dict], types: List[int]
) -> List[Dict]:
    return [q for q in questions if q.get("type") in types]


def _create_kpi_widget(
    form_id: int,
    question_id: Optional[int],
    title: str,
    rationale: str,
    col_span: int = 6,
    measure: Optional[str] = None,
) -> Dict:
    config: Dict = {
        "value_type": "number",
        "repeat_agg": "sum" if question_id else None,
    }
    if measure:
        config["measure"] = measure
    return {
        "type": "kpi",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": question_id,
        "config": config,
        "rationale": rationale,
    }


def _create_pie_widget(
    form_id: int,
    question_id: int,
    title: str,
    rationale: str,
    col_span: int = 8,
    measure: Optional[str] = None,
) -> Dict:
    config: Dict = {
        "group_by": "option",
        "variant": "doughnut",
        "color_scheme": "categorical",
    }
    if measure:
        config["measure"] = measure
    return {
        "type": "pie",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": question_id,
        "config": config,
        "rationale": rationale,
    }


def _create_bar_widget(
    form_id: int,
    question_id: int,
    title: str,
    rationale: str,
    col_span: int = 8,
    measure: Optional[str] = None,
) -> Dict:
    config: Dict = {
        "group_by": "option",
        "stack_by": None,
        "color_scheme": "categorical",
    }
    if measure:
        config["measure"] = measure
    return {
        "type": "bar",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": question_id,
        "config": config,
        "rationale": rationale,
    }


def _create_line_widget(
    form_id: int,
    date_q_id: int,
    title: str,
    rationale: str,
    col_span: int = 12,
    measure: Optional[str] = None,
) -> Dict:
    config: Dict = {
        "group_by": "month",
        "date_question_id": date_q_id,
        "color_scheme": "categorical",
    }
    if measure:
        config["measure"] = measure
    return {
        "type": "line",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": date_q_id,
        "config": config,
        "rationale": rationale,
    }


def _create_map_widget(
    form_id: int,
    title: str,
    rationale: str,
    col_span: int = 12,
) -> Dict:
    return {
        "type": "map",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": None,
        "config": {
            "map_mode": "point",
            "color_scheme": "categorical",
        },
        "rationale": rationale,
    }


def _create_table_widget(
    form_id: int,
    title: str,
    rationale: str,
    col_span: int = 24,
    questions: Optional[List[Dict]] = None,
    root_questions: Optional[List[Dict]] = None,
) -> Dict:
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
    qs = questions or []
    date_qs = _find_questions_by_type(qs, [QuestionTypes.date])
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

    indicator_types = [
        QuestionTypes.option,
        QuestionTypes.multiple_option,
        QuestionTypes.number,
        QuestionTypes.autofield,
    ]
    monitoring_indicators = [
        q for q in _find_questions_by_type(qs, indicator_types)
        if q.get("id") != date_q_id
    ]
    for q in monitoring_indicators[:3]:
        columns.append({
            "key": f"q_{q['id']}",
            "source": "answer",
            "question": q["id"],
            "label": q.get("label") or f"Question {q['id']}",
        })

    if len(monitoring_indicators) < 2 and root_questions:
        root_indicators = _find_questions_by_type(
            root_questions, indicator_types
        )
        for rq in root_indicators[:2]:
            columns.append({
                "key": f"q_{rq['id']}",
                "source": "parent_answer",
                "question": rq["id"],
                "label": rq.get("label") or f"Question {rq['id']}",
            })

    return {
        "type": "table",
        "title": title,
        "col_span": col_span,
        "color": None,
        "form": form_id,
        "question": None,
        "config": {
            "columns": columns,
            "criteria": [],
        },
        "rationale": rationale,
    }


def generate_starter_heuristics(
    metadata: Dict, user_intent: Optional[str] = None
) -> Dict:
    """Generate 4-6 widget starter layout using rule-based heuristics."""
    root_form = metadata.get("root_form", {})
    root_id = root_form.get("id")
    root_name = root_form.get("name", "Dashboard")
    root_questions = root_form.get("questions", [])

    monitoring_forms = metadata.get("monitoring_forms", [])
    has_monitoring = metadata.get("has_monitoring", bool(monitoring_forms))

    widgets: List[Dict] = []

    # 1. Headline Site Count KPI
    widgets.append(
        _create_kpi_widget(
            form_id=root_id,
            question_id=None,
            title=f"Total {root_name}",
            rationale=f"High-level count of records in {root_name}.",
            col_span=6,
        )
    )

    # 2. Metric KPI or Secondary count
    numeric_qs = _find_questions_by_type(
        root_questions, [QuestionTypes.number, QuestionTypes.autofield]
    )
    if numeric_qs:
        num_q = numeric_qs[0]
        widgets.append(
            _create_kpi_widget(
                form_id=root_id,
                question_id=num_q["id"],
                title=f"Total {num_q['label']}",
                rationale=f"Aggregated sum of {num_q['label']}.",
                col_span=6,
            )
        )
    else:
        # Default second KPI span adjustment or second count
        widgets[0]["col_span"] = 12

    # 3. Categorical Distribution (Pie / Bar)
    option_qs = _find_questions_by_type(
        root_questions, [QuestionTypes.option, QuestionTypes.autofield]
    )
    multi_qs = _find_questions_by_type(
        root_questions, [QuestionTypes.multiple_option]
    )
    all_cats = option_qs + multi_qs

    if all_cats:
        cat_q = all_cats[0]
        opt_count = cat_q.get(
            "option_count", len(cat_q.get("options", []))
        )
        if opt_count <= 5:
            widgets.append(
                _create_pie_widget(
                    form_id=root_id,
                    question_id=cat_q["id"],
                    title=f"{cat_q['label']} Breakdown",
                    rationale=f"Breakdown of sites by {cat_q['label']}.",
                    col_span=12 if len(widgets) == 1 else 12,
                )
            )
        else:
            widgets.append(
                _create_bar_widget(
                    form_id=root_id,
                    question_id=cat_q["id"],
                    title=f"{cat_q['label']} Distribution",
                    rationale=f"Distribution across {cat_q['label']}.",
                    col_span=12 if len(widgets) == 1 else 12,
                )
            )

    # Secondary Categorical if available
    if len(all_cats) > 1 and len(widgets) < 4:
        cat_q2 = all_cats[1]
        widgets.append(
            _create_bar_widget(
                form_id=root_id,
                question_id=cat_q2["id"],
                title=f"{cat_q2['label']} Overview",
                rationale=f"Categorical comparison of {cat_q2['label']}.",
                col_span=12,
            )
        )

    # 4. Monitoring Form Trends / Tables (if monitoring exists)
    if has_monitoring and monitoring_forms:
        m_form = monitoring_forms[0]
        m_id = m_form.get("id")
        m_name = m_form.get("name", "Monitoring")
        m_questions = m_form.get("questions", [])

        date_qs = _find_questions_by_type(
            m_questions, [QuestionTypes.date]
        )
        if date_qs:
            date_q = date_qs[0]
            widgets.append(
                _create_line_widget(
                    form_id=m_id,
                    date_q_id=date_q["id"],
                    title=f"{m_name} Activity Over Time",
                    rationale=f"Trend tracking by {date_q['label']}.",
                    col_span=12,
                    measure="all_submissions",
                )
            )

        # Table Overview for monitoring form
        widgets.append(
            _create_table_widget(
                form_id=m_id,
                title=f"Recent {m_name} Log",
                rationale=f"Detailed log of submissions for {m_name}.",
                col_span=24 if len(widgets) % 2 == 0 else 12,
                questions=m_questions,
                root_questions=root_questions,
            )
        )
    elif _find_questions_by_type(root_questions, [QuestionTypes.geo]):
        # Geographic map for registration forms with coordinates
        widgets.append(
            _create_map_widget(
                form_id=root_id,
                title=f"{root_name} Geographic Distribution",
                rationale=f"Spatial map locating {root_name} sites.",
                col_span=24,
            )
        )

    suggested_name = f"{root_name} Overview Dashboard"
    if user_intent:
        description = f"Starter layout tailored for: {user_intent}"
    else:
        description = (
            f"Automated starter dashboard visualizing registrations and "
            f"monitoring metrics for {root_name}."
        )

    return {
        "suggested_name": suggested_name,
        "description": description,
        "widgets": widgets,
    }


def generate_widget_heuristics(
    metadata: Dict,
    existing_widget_types: Optional[List[str]] = None,
    prompt_hint: Optional[str] = None,
) -> Dict:
    """Generate 3-5 widget suggestions prioritizing unvisualized questions."""
    existing_types = set(existing_widget_types or [])
    root_form = metadata.get("root_form", {})
    root_id = root_form.get("id")
    root_questions = root_form.get("questions", [])

    monitoring_forms = metadata.get("monitoring_forms", [])
    has_monitoring = metadata.get("has_monitoring", bool(monitoring_forms))

    suggestions: List[Dict] = []

    # 1. Check if Bar / Pie is missing
    option_qs = _find_questions_by_type(
        root_questions,
        [
            QuestionTypes.option,
            QuestionTypes.multiple_option,
            QuestionTypes.autofield,
        ],
    )
    if option_qs:
        for opt_q in option_qs[:2]:
            suggestions.append(
                _create_bar_widget(
                    form_id=root_id,
                    question_id=opt_q["id"],
                    title=f"{opt_q['label']} Comparison",
                    rationale=f"Visualizes {opt_q['label']}.",
                    col_span=12,
                )
            )

    # 2. Check if Line chart is available
    if has_monitoring and monitoring_forms:
        m_form = monitoring_forms[0]
        m_id = m_form.get("id")
        m_questions = m_form.get("questions", [])
        date_qs = _find_questions_by_type(
            m_questions, [QuestionTypes.date]
        )
        if date_qs and WidgetTypes.line not in existing_types:
            suggestions.append(
                _create_line_widget(
                    form_id=m_id,
                    date_q_id=date_qs[0]["id"],
                    title="Submission Trends",
                    rationale="Tracks chronological activity over time.",
                    col_span=12,
                    measure="all_submissions",
                )
            )

        # Table suggestion
        if WidgetTypes.table not in existing_types:
            suggestions.append(
                _create_table_widget(
                    form_id=m_id,
                    title="Escalation Status Table",
                    rationale="Tabular review for status verification.",
                    col_span=24,
                    questions=m_questions,
                    root_questions=root_questions,
                )
            )

    # 3. Numeric KPI if unrepresented
    numeric_qs = _find_questions_by_type(
        root_questions, [QuestionTypes.number]
    )
    if numeric_qs and WidgetTypes.kpi not in existing_types:
        num_q = numeric_qs[0]
        suggestions.append(
            _create_kpi_widget(
                form_id=root_id,
                question_id=num_q["id"],
                title=f"Total {num_q['label']}",
                rationale=f"Aggregated sum of {num_q['label']}.",
                col_span=6,
            )
        )

    # Ensure at least 3 suggestions
    if len(suggestions) < 3:
        suggestions.append(
            _create_kpi_widget(
                form_id=root_id,
                question_id=None,
                title="Registration Total",
                rationale="Instant KPI metric of all recorded entries.",
                col_span=6,
            )
        )

    return {
        "suggestions": suggestions[:5]
    }
