"""Structured edits of a Proposal, picked by the request's `op`.

An op changes the Proposal in place from the request body, or raises
OnboardingError. The caller re-runs every check before storing it.
Edits never call OpenAI.
"""
import re

from api.v1.v1_data_onboarding.profile import OnboardingError


def _form(proposal, body):
    form = next(
        (f for f in proposal["forms"] if f["key"] == body.get("form")), None
    )
    if not form:
        raise OnboardingError("There is no such form in this Proposal.")
    return form


def _spec(proposal, body):
    form = _form(proposal, body)
    spec = next((d for d in proposal["data"] if d["form"] == form["key"]),
                None)
    if not spec:
        raise OnboardingError("No sheet loads into this form.")
    return form, spec


def rename_form(proposal, profile, body):
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise OnboardingError("Give the form a name.")
    _form(proposal, body)["name"] = name.strip()


def drop_column(proposal, profile, body):
    """Stop loading a column: its question goes too."""
    form, spec = _spec(proposal, body)
    column = body.get("column")
    mapped = [c for c in spec["columns"] if c["column"] == column]
    if not mapped:
        raise OnboardingError("That column does not feed a question.")
    gone = {c["question"] for c in mapped}
    spec["columns"] = [c for c in spec["columns"] if c["column"] != column]
    gone -= {c["question"] for c in spec["columns"]}
    spec["value_maps"] = [
        v for v in spec["value_maps"] if v["question"] not in gone
    ]
    for group in form["question_group"]:
        group["question"] = [
            q for q in group["question"] if q["name"] not in gone
        ]
    form["question_group"] = [g for g in form["question_group"]
                              if g["question"]]
    spec["unmapped_columns"].append(
        {"column": column, "reason": "Dropped in review."}
    )


# Question types a column can be kept as without knowing its values.
KEEP_TYPES = {"number": "number", "date": "date", "text": "text"}


def keep_column(proposal, profile, body):
    """Load a column the Proposal left out, as a new optional question."""
    form, spec = _spec(proposal, body)
    column = body.get("column")
    if column not in {c["column"] for c in spec["unmapped_columns"]}:
        raise OnboardingError("That column is not left out.")
    if not form["question_group"]:
        raise OnboardingError("The form has no question group.")
    info = next(
        c for s in profile["sheets"] if s["name"] == spec["sheet"]
        for c in s["columns"] if c["name"] == column
    )
    taken = {q["name"] for g in form["question_group"]
             for q in g["question"]}
    base = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_") or "column"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}_{n}"
    form["question_group"][-1]["question"].append({
        "name": name,
        "label": column,
        "type": KEEP_TYPES.get(info["type"], "input"),
        "required": False,
        "meta": False,
        "option": [],
        "rule": None,
        "extra": None,
    })
    spec["unmapped_columns"] = [
        c for c in spec["unmapped_columns"] if c["column"] != column
    ]
    spec["columns"].append({"question": name, "column": column})


EDIT_OPS = {
    "rename_form": rename_form,
    "keep_column": keep_column,
    "drop_column": drop_column,
}
