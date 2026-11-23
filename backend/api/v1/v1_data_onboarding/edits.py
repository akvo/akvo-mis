"""Structured edits of a Proposal, picked by the request's `op`.

An op(proposal, profile, body, resolutions, blocked) changes the
Proposal and resolutions in place from the request body, or raises
OnboardingError. The caller re-runs every check before storing it.
Edits never call OpenAI. Names from the file (alias, parent and
near-match choices) go in resolutions only (see places.Places): the
Proposal goes back to OpenAI on a revision.
"""
import re

from api.v1.v1_data_onboarding.places import cut_forms, fold
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


def rename_form(proposal, profile, body, *_):
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise OnboardingError("Give the form a name.")
    _form(proposal, body)["name"] = name.strip()


def drop_column(proposal, profile, body, *_):
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


def keep_column(proposal, profile, body, *_):
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


# ------------------------------------------- Ambiguous Administration

def _get(body, key, kind=str):
    value = body.get(key)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise OnboardingError(f"'{key}' is missing or has the wrong type.")
    return value


def _units(blocked, kind):
    return [
        u for b in blocked for c in b["causes"] if c["kind"] == kind
        for u in c["units"]
    ]


def _set_location(proposal, resolutions, spec, columns, level):
    spec["administration_columns"] = columns
    resolutions.setdefault("levels", {})[spec["form"]] = level
    source = proposal["administration"]["source"]
    if not source["columns"] or source["sheet"] == spec["sheet"]:
        # Units come from the sheet whose location columns these are.
        source.update(sheet=spec["sheet"], columns=columns)


def map_level(proposal, profile, body, resolutions, blocked):
    """Location columns top-down, and the level of the first."""
    _, spec = _spec(proposal, body)
    columns = _get(body, "columns", list)
    level = _get(body, "level", int)
    if not columns or len(set(columns)) != len(columns) or \
            not all(isinstance(c, str) for c in columns) or level < 1:
        raise OnboardingError(
            "Pick distinct columns and a level below the root."
        )
    _set_location(proposal, resolutions, spec, columns, level)


def set_location_column(proposal, profile, body, resolutions, blocked):
    _, spec = _spec(proposal, body)
    _set_location(proposal, resolutions, spec, [_get(body, "column")], 1)


def drop_form(proposal, profile, body, resolutions, blocked):
    """Drop a form, with the monitoring forms that hang off it."""
    key = _form(proposal, body)["key"]
    gone = {key} | {f["key"] for f in proposal["forms"] if f["parent"] == key}
    proposal.update(cut_forms(proposal, {
        f["key"] for f in proposal["forms"] if f["key"] not in gone
    }))
    for k in gone:
        resolutions.get("levels", {}).pop(k, None)


def choose_parent(proposal, profile, body, resolutions, blocked):
    name, parent = _get(body, "name"), _get(body, "parent", int)
    if not any(fold(u["name"]) == fold(name)
               and parent in {p["id"] for p in u["parents"]}
               for u in _units(blocked, "shared_name")):
        raise OnboardingError("Pick one of the parents the review offers.")
    resolutions["parents"] = [
        p for p in resolutions.get("parents", [])
        if fold(p["name"]) != fold(name)
    ] + [{"name": name, "parent": parent}]


def resolve_near_match(proposal, profile, body, resolutions, blocked):
    """use "existing": an alias to the match; "new": add the unit."""
    name, match, use = (_get(body, k) for k in ("name", "match", "use"))
    if use not in ("existing", "new") or not any(
        fold(u["name"]) == fold(name) and fold(u["match"]) == fold(match)
        for u in _units(blocked, "near_match")
    ):
        raise OnboardingError("Pick a near-match the review offers.")
    aliases = [a for a in resolutions.get("aliases", [])
               if fold(a["from"]) != fold(name)]
    if use == "existing":
        aliases.append({"from": name, "to": match})
    else:
        resolutions.setdefault("new_units", []).append(
            {"name": name, "match": match}
        )
    resolutions["aliases"] = aliases


EDIT_OPS = {
    "rename_form": rename_form,
    "keep_column": keep_column,
    "drop_column": drop_column,
    "map_level": map_level,
    "set_location_column": set_location_column,
    "drop_form": drop_form,
    "choose_parent": choose_parent,
    "resolve_near_match": resolve_near_match,
}
