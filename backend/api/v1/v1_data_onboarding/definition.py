"""Spreadsheets that define a form rather than hold records (ADR 0002).

An XLSForm (Kobo, ODK) is parsed by the form builder's own XLSForm
import: no OpenAI. Any other layout that describes questions (an Akvo
Flow export, a paper survey, a question list) goes to OpenAI cell by
cell, but only sheets code has identified as a definition, and only
small ones. Every other sheet stays data, profiled as ADR 0001 says.
"""
import re

from api.v1.v1_data_onboarding.places import text
from api.v1.v1_data_onboarding.profile import OnboardingError
from api.v1.v1_data_onboarding.proposal import (
    DEPENDENCY_KEYS,
    QUESTION_TYPES,
)
from api.v1.v1_forms.functions import normalize_form_definition
from api.v1.v1_forms.services.xlsform_import import (
    build_form_payload,
    parse_xlsform,
    validate_preflight,
)

HEADER_ROWS = 10
# A sheet this long is records, whatever its headers say.
MAX_DEFINITION_ROWS = 1000
MAX_CELL = 500
ASKS = re.compile(r"\b(question|label)", re.I)
DEFINES = re.compile(
    r"\b(type|option|choice|answer|response|mandatory|required|hint|help"
    r"|variable|dependen|relevan|constraint|skip)", re.I,
)
# Question | Answer alone is either a paper survey, its answers left as
# lines to fill in, or records (respondent | question | answer).
ANSWERS = re.compile(r"\b(answer|response)", re.I)
LINE = re.compile(r"_{3,}")


def no_administration():
    return {"levels": [], "source": {"sheet": None, "columns": []},
            "aliases": []}


def grids(raw):
    """{sheet: rows of text-or-None cells} from header-less DataFrames."""
    result = {}
    for sheet, df in raw.items():
        rows = []
        for values in df.itertuples(index=False):
            row = [None if v is None else text(v) or None for v in values]
            while row and row[-1] is None:
                row.pop()
            if row:
                rows.append(row)
        result[sheet] = rows
    return result


def _header(row):
    """How many definition headers the row has; 0 unless it is a header.

    A header row has two different ones: one names the question, one
    describes it.
    """
    cells = {c for c in row if c and len(c) <= 40}
    asks = {c for c in cells if ASKS.search(c)}
    defines = {c for c in cells if DEFINES.search(c)}
    if asks and defines and len(asks | defines) >= 2:
        return len(asks | defines)
    return 0


def _header_index(rows):
    """The row of the first HEADER_ROWS with the most headers."""
    scores = [_header(row) for row in rows[:HEADER_ROWS]]
    return scores.index(max(scores))


def _names(rows, h):
    """Column names: the header, after its group header when one spans
    it (the row above, when that row has two or more cells)."""
    above = rows[h - 1] if h and sum(1 for c in rows[h - 1] if c) > 1 \
        else []
    names, seen, group = [], {}, None
    for i, cell in enumerate(rows[h]):
        group = (above[i] if i < len(above) and above[i] else group)
        name = cell or f"column {i + 1}"
        if group and group != name:
            name = f"{group}: {name}"
        seen[name] = seen.get(name, 0) + 1
        names.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return names


def is_xlsform(sheets):
    survey = next((rows for name, rows in sheets.items()
                   if name.lower() == "survey"), None)
    head = {(c or "").lower() for c in (survey or [[]])[0]}
    return {"type", "name"} <= head


def _answered(row, rows):
    """Whether "Answer" is the header's only description and its column
    holds answers, not lines to fill in: records."""
    defines = [j for j, c in enumerate(row) if c and DEFINES.search(c)]
    if not all(ANSWERS.search(row[j]) for j in defines):
        return False
    return any(j < len(r) and r[j] and not LINE.search(r[j])
               for r in rows for j in defines)


def _holds_records(header, defined):
    """A header row mostly naming the definition's own cells (a codebook's
    variables): the records it describes."""
    cells = [c.casefold() for c in header if c]
    return len(cells) >= 2 and \
        sum(1 for c in cells if c in defined) / len(cells) >= .5


def definition_sheets(sheets):
    """Names of sheets that describe questions, in workbook order.

    None when another sheet holds the records they describe (data plus a
    codebook): the file is data.
    """
    names, defined = [], set()
    for name, rows in sheets.items():
        if len(rows) > MAX_DEFINITION_ROWS or \
                not any(_header(row) for row in rows[:HEADER_ROWS]):
            continue
        h = _header_index(rows)
        if _answered(rows[h], rows[h + 1:]):
            continue
        names.append(name)
        defined |= {c.casefold() for row in rows[h + 1:] for c in row if c}
    if any(_holds_records(rows[0], defined)
           for name, rows in sheets.items() if name not in names and rows):
        return []
    return names


def layout_content(sheets, names):
    """What OpenAI reads of definition sheets: their cells, trimmed.

    The rows above the header go as they are; every row after it as
    {column name: cell}, filled cells only, so no cell is read under
    the wrong header.
    """
    def cut(c):
        return c[:MAX_CELL]

    content = []
    for name in names:
        rows = sheets[name]
        h = _header_index(rows)
        columns = _names(rows, h)
        content.append({
            "name": name,
            "above_header": [[cut(c) if c else None for c in row]
                             for row in rows[:h]],
            "rows": [
                {(columns[i] if i < len(columns) else f"column {i + 1}"):
                 cut(c) for i, c in enumerate(row) if c}
                for row in rows[h + 1:]
            ],
        })
    return {"sheets": content}


def _title(sheets, file_name):
    settings = next((rows for name, rows in sheets.items()
                     if name.lower() == "settings"), [])
    if len(settings) >= 2:
        row = dict(zip([(c or "").lower() for c in settings[0]],
                       settings[1]))
        for key in ("form_title", "title", "id_string", "form_id"):
            if row.get(key):
                return row[key].replace("_", " ").strip().capitalize()
    return file_name.rsplit(".", 1)[0]


def _dependency(dep, names):
    if dep.get("id") not in names:
        return None
    rule = {key: dep.get(key) for key in DEPENDENCY_KEYS}
    for key in ("equal", "notEqual"):
        if rule[key] is not None:
            rule[key] = str(rule[key])
    options = [str(o) for o in dep.get("options") or []]
    if not options and all(v is None for v in rule.values()):
        return None
    return {"question": names[dep["id"]], "options": options, **rule}


def _question(q, names):
    rule = q.get("rule") or {}
    return {
        "name": q["name"],
        "label": q.get("label") or q["name"],
        "type": q["type"],
        "required": bool(q.get("required")),
        "meta": bool(q.get("meta")),
        "option": [{"label": o["label"], "value": str(o["value"])}
                   for o in q.get("option") or []],
        "rule": {
            "min": rule.get("min"), "max": rule.get("max"),
            "allowDecimal": bool(rule.get("allowDecimal")),
        } if q["type"] == "number" else None,
        "extra": None,
        "tooltip": q.get("tooltip"),
        "dependency": [d for d in (
            _dependency(dep, names) for dep in q.get("dependency") or []
        ) if d],
        "dependency_rule": q.get("dependency_rule") or "AND",
    }


def xlsform_proposal(path, sheets, file_name):
    """A forms-only Proposal from an XLSForm, through the form import."""
    try:
        parsed = parse_xlsform(path)
    except ValueError as exc:
        raise OnboardingError(f"The XLSForm could not be read: {exc}")
    errors, _ = validate_preflight(parsed)
    if errors:
        raise OnboardingError(
            f"The XLSForm could not be read: {errors[0]['message']}"
        )
    form = normalize_form_definition(build_form_payload(parsed))
    kept = [q for g in form["question_group"] for q in g["question"]
            if q["type"] in QUESTION_TYPES]
    names = {q["id"]: q["name"] for q in kept}
    groups = []
    for g in form["question_group"]:
        questions = [_question(q, names) for q in g["question"]
                     if q["id"] in names]
        if questions:
            groups.append({
                "name": g["name"], "label": g.get("label") or g["name"],
                "repeatable": bool(g.get("repeatable")),
                "question": questions,
            })
    if not groups:
        raise OnboardingError("The XLSForm has no questions MIS can hold.")
    dropped = sorted(
        q["name"] for g in form["question_group"] for q in g["question"]
        if q["id"] not in names
    )
    name = parsed["form_name"]
    if name == "Imported Form":  # the import's fallback: no title set
        name = _title(sheets, file_name)
    notes = ["Read as an XLSForm: the questions, groups, options, rules and"
             " conditions come from the file as written."]
    if dropped:
        notes.append("Left out, as MIS has no such question type: "
                     + ", ".join(dropped) + ".")
    notes += [w["message"] for w in parsed.get("skipped_rows", [])]
    return {
        "administration": no_administration(),
        "forms": [{"key": "form", "name": name, "type": "registration",
                   "parent": None, "question_group": groups}],
        "data": [],
        "notes": notes,
    }
