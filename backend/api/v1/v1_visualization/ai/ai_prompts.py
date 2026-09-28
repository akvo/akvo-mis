import html
import json
import re

# =========================================================
# AI Prompts & JSON Schema Definitions (VIZ-AI-002)
# =========================================================

MAX_USER_INTENT_LENGTH = 250

DASHBOARD_DESIGN_SYSTEM_PROMPT = (
    "You are an expert Data Visualization Architect for Akvo MIS.\n"
    "Your task is to analyze the provided Form Family schema (a root "
    "registration form and optional child monitoring forms) and recommend a "
    "cohesive, insightful starter dashboard layout.\n\n"
    "CRITICAL ARCHITECTURAL & DESIGN RULES:\n"
    "1. STRICT REFERENTIAL INTEGRITY:\n"
    "   - Every widget MUST reference a valid `form` ID (integer) from "
    "the schema.\n"
    "   - Every widget with a `question` MUST reference a valid `question` "
    "ID (integer) belonging to that specified `form`.\n"
    "   - Never invent or hallucinate form or question IDs.\n\n"
    "2. MULTI-LINGUAL LANGUAGE PARITY:\n"
    "   - You MUST analyze the natural language of the question labels in "
    "the form definition (e.g. English, French, Spanish, Bahasa Indonesia, "
    "Swahili).\n"
    "   - Generate all widget `title`, dashboard `suggested_name`, "
    "`description`, and `rationale` in the EXACT SAME LANGUAGE as the form "
    "labels.\n\n"
    "3. APPROPRIATE VISUAL ENCODING:\n"
    "   - Headline / Total Counts: Use `type: \"kpi\"` (col_span: 6 or 12).\n"
    "     - Site count / registration total: `question: null`, `config: "
    "{\"value_type\": \"number\"}`.\n"
    "     - Numeric metrics: `form: <form_id>`, `question: "
    "<question_id>`, `config: {\"value_type\": \"number\", "
    "\"repeat_agg\": \"sum\"|\"average\"}`.\n"
    "   - Categorical Distributions:\n"
    "     - 2 to 5 choices: Use `type: \"pie\"` (col_span: 8 or 12), `config: "
    "{\"group_by\": \"option\", \"variant\": \"doughnut\", \"color_scheme\": "
    "\"categorical\"}`.\n"
    "     - 6+ choices: Use `type: \"bar\"` (col_span: 8 or 12), `config: "
    "{\"group_by\": \"option\", \"stack_by\": null, \"color_scheme\": "
    "\"categorical\"}`.\n"
    "   - Temporal Trends:\n"
    "     - Date questions on monitoring forms: Use `type: \"line\"` "
    "(col_span: 12 or 24), `config: {\"group_by\": \"month\", "
    "\"date_question_id\": <question_id>, \"color_scheme\": "
    "\"categorical\"}`.\n"
    "   - Geographic Maps:\n"
    "     - If form has geolocation questions (type: 5 / geo): Use "
    "`type: \"map\"` (col_span: 24), `question: <geo_question_id_or_null>`, "
    "`config: {\"map_mode\": \"category\", \"color_scheme\": "
    "\"categorical\"}`.\n"
    "   - Continuous Metric Correlations / Scatter Plots:\n"
    "     - When comparing two continuous numeric metrics: Use "
    "`type: \"scatter\"` (col_span: 12), `question: <x_question_id>`, "
    "`config: {\"question_y\": <y_question_id>, "
    "\"color_scheme\": \"categorical\"}`.\n"
    "   - Escalation / Monitoring Tables:\n"
    "     - Use `type: \"table\"` (col_span: 24), `question: null`, ONLY on "
    "child monitoring forms.\n"
    "     - `config.columns` MUST be pre-populated with standard columns:\n"
    "       - parent_name: `{\"key\": \"parent_name\", \"source\": "
    "\"parent_name\", \"label\": \"Datapoint name\"}`\n"
    "       - administration: `{\"key\": \"administration\", \"source\": "
    "\"administration\", \"label\": \"Administration\"}`\n"
    "       - date (if any): `{\"key\": \"q_<id>\", \"source\": "
    "\"latest_date\", \"question\": <id>, \"label\": \"Last submission\"}`\n"
    "       - indicators: `{\"key\": \"q_<id>\", \"source\": \"answer\", "
    "\"question\": <id>, \"label\": \"<label>\"}`\n"
    "     - `config.criteria: []`.\n\n"
    "4. VISUAL DIVERSITY & PALETTE BALANCE:\n"
    "   - A starter dashboard must contain 4 to 6 complementary widgets.\n"
    "   - Do NOT generate more than 2 widgets of the same chart type.\n"
    "   - Provide a diverse multi-tier composition (e.g. 2 KPIs at the top, "
    "2 distribution charts in the middle, 1 trend/map/table at bottom).\n\n"
    "5. FORM SCOPE & MEASURE RULES:\n"
    "   - For child monitoring forms (`form != root_form_id`), "
    "ALWAYS set `config.measure: \"all_submissions\"` for line charts or "
    "`config.measure: \"current_state\"` for bar/pie/kpi charts.\n"
    "   - For the root registration form (`form == root_form_id`), "
    "NEVER set `measure` (omit or set to null).\n"
    "   - If `has_monitoring: false`, NEVER generate `table` widgets.\n\n"
    "6. OUTPUT FORMAT:\n"
    "   - Respond ONLY with a valid JSON object matching this schema:\n"
    "     {\n"
    "       \"suggested_name\": \"string\",\n"
    "       \"description\": \"string\",\n"
    "       \"widgets\": [\n"
    "         {\n"
    "           \"type\": \"kpi\" | \"pie\" | \"bar\" |\n"
    "                   \"line\" | \"table\" | \"map\" | \"scatter\",\n"
    "           \"title\": \"string\",\n"
    "           \"col_span\": 6 | 8 | 12 | 24,\n"
    "           \"form\": integer,\n"
    "           \"question\": integer | null,\n"
    "           \"config\": { ... },\n"
    "           \"rationale\": \"string\"\n"
    "         }\n"
    "       ]\n"
    "     }"
)

WIDGET_SUGGESTION_SYSTEM_PROMPT = (
    "You are an expert Data Visualization Architect for Akvo MIS.\n"
    "Your task is to analyze an existing dashboard canvas along with the "
    "form family schema and recommend 3 to 5 complementary widgets based on "
    "user intent.\n\n"
    "RULES:\n"
    "1. USER INTENT PRECEDENCE (CRITICAL):\n"
    "   - If the user specifies a particular chart type (e.g. \"map\", "
    "\"scatter\", \"trend\"/\"line\", \"pie\", \"bar\", \"table\", \"kpi\") "
    "or topic (e.g. \"location\"/\"gps\", \"correlation\"), you MUST "
    "generate that requested widget type as the primary first suggestion "
    "(`suggestions[0]`).\n"
    "   - Secondary suggestions should complement the canvas with other "
    "unvisualized questions.\n\n"
    "2. VISUAL ENCODING BY CHART TYPE:\n"
    "   - `map`: Use when location/GPS is requested or for `type_name: "
    "\"geo\"` fields. `col_span: 24`, `question: <geo_question_id_or_null>`, "
    "`config: {\"map_mode\": \"point\", \"color_scheme\": "
    "\"categorical\"}`.\n"
    "   - `scatter`: Use when correlation between two continuous metrics is "
    "requested. `col_span: 12`, `question: <x_question_id>`, `config: "
    "{\"question_y\": <y_question_id>, \"color_scheme\": "
    "\"categorical\"}`.\n"
    "   - `pie`: Use for categorical breakdowns (2-5 options). `col_span: 8` "
    "or `12`, `config: {\"group_by\": \"option\", \"variant\": \"doughnut\", "
    "\"color_scheme\": \"categorical\"}`.\n"
    "   - `bar`: Use for categorical distributions (6+ options). `col_span: "
    "8` or `12`, `config: {\"group_by\": \"option\", \"stack_by\": null, "
    "\"color_scheme\": \"categorical\"}`.\n"
    "   - `line`: Use for temporal activity over time. `col_span: 12` "
    "or `24`, `config: {\"group_by\": \"month\", \"date_question_id\": "
    "<date_id>, \"color_scheme\": \"categorical\"}`.\n"
    "   - `kpi`: Use for headline counts / numeric aggregates. `col_span: 6` "
    "or `12`, `config: {\"value_type\": \"number\"}`.\n"
    "   - `table`: Use for tabular monitoring logs (on child monitoring forms "
    "only). `col_span: 24`, `question: null`.\n\n"
    "3. FORM SCOPE & MEASURE:\n"
    "   - For child monitoring forms (`form != root_form_id`), set "
    "`config.measure: \"all_submissions\"` for line charts or "
    "`config.measure: \"current_state\"` for bar/pie/kpi.\n"
    "   - For root registration forms, omit `measure`.\n\n"
    "4. OUTPUT FORMAT:\n"
    "   - Respond ONLY with a valid JSON object matching this schema:\n"
    "   {\n"
    "     \"suggestions\": [\n"
    "       {\n"
    "         \"type\": \"kpi\" | \"pie\" | \"bar\" |\n"
    "                 \"line\" | \"table\" | \"map\" | \"scatter\",\n"
    "         \"title\": \"string\",\n"
    "         \"col_span\": 6 | 8 | 12 | 24,\n"
    "         \"form\": integer,\n"
    "         \"question\": integer | null,\n"
    "         \"config\": { ... },\n"
    "         \"rationale\": \"string\"\n"
    "       }\n"
    "     ]\n"
    "   }"
)


def sanitize_user_input(text: str) -> str:
    """Sanitize free-text user intent to prevent prompt injection."""
    if not text:
        return ""
    # Strip dangerous control characters but preserve standard punctuation
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(text).strip())
    # HTML escape
    escaped = html.escape(clean)
    # Truncate to max length after escaping
    return escaped[:MAX_USER_INTENT_LENGTH]


def build_starter_dashboard_prompt(
    family_metadata: dict, user_intent: str = None
) -> list:
    """Construct structured messages array for starter dashboard."""
    sanitized_intent = sanitize_user_input(user_intent)
    formatted_schema = json.dumps(family_metadata, indent=2)

    user_content_parts = [
        "FORM FAMILY SCHEMA METADATA (JSON):",
        f"```json\n{formatted_schema}\n```"
    ]

    if sanitized_intent:
        user_content_parts.append(
            "\nUSER INTENT / SPECIFIC FOCUS:\n"
            f"<user_intent>{sanitized_intent}</user_intent>"
        )
    else:
        user_content_parts.append(
            "\nUSER INTENT:\n"
            "<user_intent>Generate a standard comprehensive overview starter "
            "dashboard.</user_intent>"
        )

    return [
        {"role": "system", "content": DASHBOARD_DESIGN_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_content_parts)},
    ]


def build_widget_suggestion_prompt(
    family_metadata: dict,
    existing_widget_types: list = None,
    prompt_hint: str = None
) -> list:
    """Construct structured messages for in-canvas widget suggestions."""
    sanitized_hint = sanitize_user_input(prompt_hint)
    formatted_schema = json.dumps(family_metadata, indent=2)

    types_str = str(existing_widget_types or [])
    user_content_parts = [
        "FORM FAMILY SCHEMA METADATA (JSON):",
        f"```json\n{formatted_schema}\n```",
        f"\nCURRENTLY EXISTING WIDGET TYPES ON CANVAS:\n{types_str}"
    ]

    if sanitized_hint:
        user_content_parts.append(
            f"\nUSER FOCUS HINT:\n<user_intent>{sanitized_hint}</user_intent>"
        )

    return [
        {"role": "system", "content": WIDGET_SUGGESTION_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_content_parts)},
    ]


# Standard JSON Object response format for OpenAI
STARTER_DASHBOARD_JSON_SCHEMA = {"type": "json_object"}
WIDGET_SUGGESTION_JSON_SCHEMA = {"type": "json_object"}
