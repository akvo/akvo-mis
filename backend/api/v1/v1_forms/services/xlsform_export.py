import io
import openpyxl
from typing import Tuple, List, Dict, Any, Optional
from api.v1.v1_forms.constants import QuestionTypes

_XLSFORM_COLUMNS = [
    "type",
    "name",
    "label",
    "required",
    "hint",
    "relevant",
    "constraint",
    "constraint_message",
    "choice_filter",
    "parameters",
    "appearance",
    "calculation",
    "default",
    "repeat_count",
]


def _map_type(question: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Maps Akvo MIS question type to (xlsform_type_str, appearance_or_None).
    Returns (None, None) for skipped types (tree, table, autofield).
    """
    qtype = question.type
    rule = getattr(question, "rule", None) or {}
    q_name = (
        getattr(question, "name", None)
        or f"q_{getattr(question, 'id', 'unknown')}"
    )

    if qtype in (QuestionTypes.text, QuestionTypes.input):
        return ("text", None)
    elif qtype == QuestionTypes.number:
        if rule.get("allowDecimal"):
            return ("decimal", None)
        return ("integer", None)
    elif qtype == QuestionTypes.date:
        return ("date", None)
    elif qtype == QuestionTypes.option:
        has_other = False
        opts_mgr = getattr(question, "question_question_option", None)
        if opts_mgr and hasattr(opts_mgr, "all"):
            has_other = any(opt.other for opt in opts_mgr.all())
        suffix = " or_other" if has_other else ""
        return (f"select_one option_{q_name}{suffix}", None)
    elif qtype == QuestionTypes.multiple_option:
        has_other = False
        opts_mgr = getattr(question, "question_question_option", None)
        if opts_mgr and hasattr(opts_mgr, "all"):
            has_other = any(opt.other for opt in opts_mgr.all())
        suffix = " or_other" if has_other else ""
        return (f"select_multiple option_{q_name}{suffix}", None)
    elif qtype == QuestionTypes.geo:
        return ("geopoint", None)
    elif qtype == QuestionTypes.geoshape:
        return ("geoshape", None)
    elif qtype == QuestionTypes.geotrace:
        return ("geotrace", None)
    elif qtype == QuestionTypes.image:
        return ("image", None)
    elif qtype == QuestionTypes.attachment:
        return ("file", None)
    elif qtype == QuestionTypes.signature:
        return ("image", "signature")
    elif qtype == QuestionTypes.cascade:
        return ("select_one_from_file administration.csv", None)
    elif qtype in (
        QuestionTypes.tree,
        QuestionTypes.table,
        QuestionTypes.autofield,
    ):
        return (None, None)

    return ("text", None)


def _build_question_map(form: Any) -> Dict[int, Dict[str, Any]]:
    """
    Pre-pass building a map of {question_id: {"name": name, "type": type}}
    for dependency ID -> question name resolution.
    """
    question_map = {}
    for group in form.form_question_group.all():
        for q in group.question_group_question.all():
            question_map[q.id] = {
                "name": q.name or f"q_{q.id}",
                "type": q.type,
            }
    return question_map


def _build_settings_row(form: Any) -> Dict[str, Any]:
    """
    Builds the form metadata for the settings sheet.
    """
    return {
        "form_title": form.name or f"Form {form.id}",
        "form_id": f"form_{form.id}",
        "version": str(form.version or 1),
        "default_language": form.default_language or "en",
    }


def _build_choices_rows(
    form: Any, lang_cols: List[str]
) -> List[Dict[str, Any]]:
    """
    Builds list of choice dicts for select_one / select_multiple options.
    """
    choices = []
    for group in form.form_question_group.all():
        for q in group.question_group_question.all():
            if q.type in (QuestionTypes.option, QuestionTypes.multiple_option):
                list_name = f"option_{q.name or f'q_{q.id}'}"
                options = q.question_question_option.all()
                for opt in options:
                    if opt.other:
                        continue
                        # 'or_other' handles the 'other'
                        # choice automatically in XLSForm
                    row = {
                        "list_name": list_name,
                        "name": str(
                            opt.value if opt.value is not None else opt.id
                        ),
                        "label": opt.label or str(opt.value),
                    }
                    # Handle translations for options if present
                    if opt.translations and isinstance(opt.translations, dict):
                        for lang_code in lang_cols:
                            trans = opt.translations.get(lang_code, {})
                            if isinstance(trans, dict) and "label" in trans:
                                row[f"label::{lang_code}"] = trans["label"]
                    choices.append(row)
    return choices


def _build_relevant_expression(
    question: Any, question_map: Dict[int, Dict[str, Any]]
) -> str:
    """
    Converts question.dependency JSON list into an
    XLSForm XPath 'relevant' expression.
    Supported dependency conditions:
    - options (single or list) -> selected(${name}, 'val')
    - min -> ${name} >= N
    - max -> ${name} <= N
    - equal -> ${name} = 'val'
    - notEqual -> ${name} != 'val' and string-length(${name}) > 0
    Combined by dependency_rule ('AND' or 'OR', default 'AND').
    """
    deps = getattr(question, "dependency", None)
    if not deps or not isinstance(deps, list):
        return ""

    rule = (getattr(question, "dependency_rule", None) or "AND").upper()
    joiner = " or " if rule == "OR" else " and "

    expr_parts = []
    for dep in deps:
        if not isinstance(dep, dict):
            continue

        q_id = dep.get("id")
        if q_id not in question_map:
            continue

        q_target = question_map[q_id]
        target_name = q_target["name"]

        # 1. options condition
        if "options" in dep:
            opts = dep["options"]
            if isinstance(opts, list) and len(opts) > 0:
                if len(opts) == 1:
                    expr_parts.append(
                        f"selected(${{{target_name}}}, '{opts[0]}')"
                    )
                else:
                    sub = " or ".join(
                        f"selected(${{{target_name}}}, '{v}')" for v in opts
                    )
                    expr_parts.append(f"({sub})")

        # 2. min condition
        if "min" in dep:
            min_val = dep["min"]
            expr_parts.append(f"${{{target_name}}} >= {min_val}")

        # 3. max condition
        if "max" in dep:
            max_val = dep["max"]
            expr_parts.append(f"${{{target_name}}} <= {max_val}")

        # 4. equal condition
        if "equal" in dep:
            eq_val = dep["equal"]
            expr_parts.append(f"${{{target_name}}} = '{eq_val}'")

        # 5. notEqual condition
        if "notEqual" in dep:
            neq_val = dep["notEqual"]
            expr_parts.append(
                f"${{{target_name}}} != '{neq_val}' and string-length(${{{target_name}}}) > 0"  # noqa
            )

    return joiner.join(expr_parts)


def _build_survey_rows(
    form: Any, question_map: Dict[int, Dict[str, Any]], lang_cols: List[str]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Builds flat list of survey sheet row dicts
    (begin/end group/repeat + question rows).
    Returns (survey_rows, skipped_question_names).
    """
    survey_rows = []
    skipped = []

    for group in form.form_question_group.all():
        g_name = group.name or f"group_{group.id}"
        g_is_repeat = bool(group.repeatable)

        # Emit begin_repeat / begin_group
        begin_type = "begin_repeat" if g_is_repeat else "begin_group"
        begin_row = {
            "type": begin_type,
            "name": g_name,
            "label": group.label or g_name,
        }
        if group.translations and isinstance(group.translations, dict):
            for lang_code in lang_cols:
                trans = group.translations.get(lang_code, {})
                if isinstance(trans, dict) and "label" in trans:
                    begin_row[f"label::{lang_code}"] = trans["label"]
        survey_rows.append(begin_row)

        for q in group.question_group_question.all():
            q_name = q.name or f"q_{q.id}"
            xls_type, appearance = _map_type(q)

            if xls_type is None:
                skipped.append(q_name)
                continue

            relevant_expr = _build_relevant_expression(q, question_map)

            q_row = {
                "type": xls_type,
                "name": q_name,
                "label": q.label or q_name,
                "required": "yes" if q.required else "no",
            }
            if relevant_expr:
                q_row["relevant"] = relevant_expr
            if appearance:
                q_row["appearance"] = appearance

            # Tooltip -> hint
            if (
                q.tooltip
                and isinstance(q.tooltip, dict)
                and q.tooltip.get("text")
            ):
                q_row["hint"] = q.tooltip["text"]

            # Translations
            if q.translations and isinstance(q.translations, dict):
                for lang_code in lang_cols:
                    trans = q.translations.get(lang_code, {})
                    if isinstance(trans, dict):
                        if "label" in trans:
                            q_row[f"label::{lang_code}"] = trans["label"]
                        if (
                            "tooltip" in trans
                            and isinstance(trans["tooltip"], dict)
                            and trans["tooltip"].get("text")
                        ):
                            q_row[f"hint::{lang_code}"] = trans["tooltip"][
                                "text"
                            ]

            survey_rows.append(q_row)

        # Emit end_repeat / end_group
        end_type = "end_repeat" if g_is_repeat else "end_group"
        survey_rows.append({"type": end_type})

    return survey_rows, skipped


def generate_xlsform(form: Any) -> Tuple[io.BytesIO, List[str]]:
    """
    Public entrypoint: generates XLSForm workbook for a given form.
    Returns (BytesIO_excel_stream, skipped_question_names).
    """
    wb = openpyxl.Workbook()
    # default sheet
    ws_survey = wb.active
    ws_survey.title = "survey"
    ws_choices = wb.create_sheet(title="choices")
    ws_settings = wb.create_sheet(title="settings")

    lang_cols = form.languages or []
    question_map = _build_question_map(form)

    # 1. Settings Sheet
    settings_data = _build_settings_row(form)
    ws_settings.append(list(settings_data.keys()))
    ws_settings.append(list(settings_data.values()))

    # 2. Survey Sheet
    survey_rows, skipped = _build_survey_rows(form, question_map, lang_cols)

    # Build dynamic columns (base + multilingual label/hint)
    cols = list(_XLSFORM_COLUMNS)
    for code in lang_cols:
        lbl_col = f"label::{code}"
        hint_col = f"hint::{code}"
        if lbl_col not in cols:
            cols.append(lbl_col)
        if hint_col not in cols:
            cols.append(hint_col)

    ws_survey.append(cols)
    for row in survey_rows:
        ws_survey.append([row.get(col, "") for col in cols])

    # 3. Choices Sheet
    choices_rows = _build_choices_rows(form, lang_cols)
    choice_cols = ["list_name", "name", "label"]
    for code in lang_cols:
        col = f"label::{code}"
        if col not in choice_cols:
            choice_cols.append(col)

    ws_choices.append(choice_cols)
    for row in choices_rows:
        ws_choices.append([row.get(col, "") for col in choice_cols])

    # Save to BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return output, skipped
