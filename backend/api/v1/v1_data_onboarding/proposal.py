"""The Proposal format and its validator.

SCHEMA is sent to OpenAI as a strict structured-output schema, and
validate_proposal checks any Proposal (drafted or edited) before it is
stored. Forms are canonical form definitions, as the form definition
import accepts them, plus a `key` the data specs refer to.
Administration and data follow the plan.json sections from #462. Maps
are lists of pairs, because strict schemas cannot have free-form keys.
"""
from api.v1.v1_forms.functions import (
    normalize_form_definition,
    validate_form_definition,
)

QUESTION_TYPES = [
    "input", "text", "number", "option", "multiple_option", "date", "geo",
    "cascade",
]


def _obj(**props):
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def _arr(items):
    return {"type": "array", "items": items}


def _null(schema):
    return {"anyOf": [schema, {"type": "null"}]}


STR = {"type": "string"}
NUM = {"type": "number"}
BOOL = {"type": "boolean"}

QUESTION = _obj(
    name=STR,
    label=STR,
    type={"type": "string", "enum": QUESTION_TYPES},
    required=BOOL,
    meta=BOOL,
    option=_arr(_obj(label=STR, value=STR)),
    rule=_null(_obj(min=_null(NUM), max=_null(NUM), allowDecimal=BOOL)),
    # The administration question: type cascade, extra.type administration.
    extra=_null(_obj(type={"type": "string", "enum": ["administration"]})),
)

FORM = _obj(
    key=STR,
    name=STR,
    type={"type": "string", "enum": ["registration", "monitoring"]},
    parent=_null(STR),  # key of the registration form, for monitoring
    question_group=_arr(_obj(name=STR, label=STR, question=_arr(QUESTION))),
)

DATA = _obj(
    form=STR,
    sheet=STR,
    key_columns=_arr(STR),
    # Monitoring only: the columns holding the parent record's key, in
    # the order of the parent sheet's key_columns.
    parent_key_columns=_arr(STR),
    administration_columns=_arr(STR),
    geo=_null(_obj(lat=_null(STR), lng=_null(STR), column=_null(STR))),
    columns=_arr(_obj(question=STR, column=STR)),
    value_maps=_arr(
        _obj(question=STR, values=_arr(_obj(raw=STR, label=STR)))
    ),
    date_format=_null(STR),
    multi_separator={**_null(STR), "description": (
        "The characters that separate choices in a multi-select cell; each"
        " character splits on its own (not a pattern). Null: any of ;,|/"
    )},
    unmapped_columns=_arr(_obj(column=STR, reason=STR)),
)

SCHEMA = _obj(
    administration=_obj(
        levels=_arr(STR),
        source=_obj(sheet=_null(STR), columns=_arr(STR)),
        aliases=_arr(_obj(**{"from": STR, "to": STR})),
    ),
    forms=_arr(FORM),
    data=_arr(DATA),
    notes=_arr(STR),
)


def _shape_errors(schema, value, path):
    if "anyOf" in schema:
        if any(not _shape_errors(s, value, path) for s in schema["anyOf"]):
            return []
        return [f"{path}: has the wrong type"]
    kind = schema["type"]
    if kind == "null":
        ok = value is None
    elif kind == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        ok = isinstance(value, {
            "object": dict, "array": list, "string": str, "boolean": bool,
        }[kind])
    if not ok:
        return [f"{path}: must be {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: must be one of {', '.join(schema['enum'])}"]
    errors = []
    if kind == "object":
        if set(value) != set(schema["properties"]):
            keys = ", ".join(schema["required"])
            return [f"{path}: must have exactly {keys}"]
        for key, sub in schema["properties"].items():
            errors += _shape_errors(sub, value[key], f"{path}.{key}")
    elif kind == "array":
        for i, item in enumerate(value):
            errors += _shape_errors(schema["items"], item, f"{path}[{i}]")
    return errors


def validate_proposal(proposal, profile):
    """Return a list of error messages; empty means valid.

    A well-shaped Proposal is normalized in place first. Messages name
    columns and questions, never cell values.
    """
    errors = _shape_errors(SCHEMA, proposal, "proposal")
    if errors:
        return errors
    normalize(proposal, profile)

    sheets = {
        s["name"]: {c["name"]: c for c in s["columns"]}
        for s in profile["sheets"]
    }

    def check_columns(path, sheet, names):
        for name in names:
            if name not in sheet:
                errors.append(f"{path}: column '{name}' is not in the sheet")

    source = proposal["administration"]["source"]
    if source["columns"]:
        if source["sheet"] not in sheets:
            errors.append("administration.source: unknown sheet")
        else:
            check_columns(
                "administration.source", sheets[source["sheet"]],
                source["columns"],
            )

    forms = {}
    for i, form in enumerate(proposal["forms"]):
        if form["key"] in forms:
            errors.append(f"forms[{i}]: key '{form['key']}' is used twice")
        forms[form["key"]] = form
        for issue in validate_form_definition(
            normalize_form_definition(form)
        ):
            if issue["level"] == "error":
                errors.append(
                    f"forms[{i}].{issue['path']}: {issue['message']}"
                )

    for i, form in enumerate(proposal["forms"]):
        parent = forms.get(form["parent"])
        if form["type"] == "monitoring" and (
            not parent or parent["type"] != "registration"
        ):
            errors.append(
                f"forms[{i}].parent: must be the key of a registration"
                " form in this Proposal"
            )
        if form["type"] == "registration" and form["parent"] is not None:
            errors.append(f"forms[{i}].parent: must be null on registration")

    specs = {s["form"]: s for s in proposal["data"]}
    for i, form in enumerate(proposal["forms"]):
        if form["key"] not in specs:
            errors.append(f"forms[{i}]: no data spec loads '{form['key']}'")
    for i, spec in enumerate(proposal["data"]):
        path = f"data[{i}]"
        form = forms[spec["form"]]  # normalize dropped unknown forms
        sheet = sheets.get(spec["sheet"])
        if sheet is None:
            errors.append(f"{path}: unknown sheet '{spec['sheet']}'")
            continue
        parent = specs.get(form["parent"])
        if form["type"] == "monitoring" and (
            not parent
            or len(spec["parent_key_columns"]) != len(parent["key_columns"])
        ):
            errors.append(
                f"{path}.parent_key_columns: must match the parent sheet's"
                " key_columns"
            )
        geo = spec["geo"] or {}
        check_columns(
            path, sheet,
            spec["key_columns"] + spec["parent_key_columns"]
            + spec["administration_columns"]
            + [c for c in geo.values() if c]
            + [c["column"] for c in spec["columns"]]
            + [c["column"] for c in spec["unmapped_columns"]],
        )
    return errors


def _is_location(question):
    return question["type"] == "cascade" and \
        (question["extra"] or {}).get("type") == "administration"


def normalize(proposal, profile):
    """Fix what models draft wrong but code can settle. On a valid shape.

    Models drop or mangle parts of a Proposal at random:
    - a data spec for a form that is not there loads nothing: it goes;
    - a column fed to a question the form lacks is not loaded, and is
      listed so with a reason the review shows;
    - location columns fed to the administration question move to
      `administration_columns`, top level first;
    - value maps and options for columns whose values were never sent
      are made up: the maps go, and the question takes text;
    - a column in use is not listed as not loaded.
    """
    sheets = {
        s["name"]: {c["name"]: c for c in s["columns"]}
        for s in profile["sheets"]
    }
    forms = {f["key"]: f for f in proposal["forms"]}
    proposal["data"] = [d for d in proposal["data"] if d["form"] in forms]
    source = proposal["administration"]["source"]
    for spec in proposal["data"]:
        form = forms[spec["form"]]
        questions = {q["name"]: q for g in form["question_group"]
                     for q in g["question"]}
        for c in spec["columns"]:
            if c["question"] not in questions:
                spec["unmapped_columns"].append({
                    "column": c["column"],
                    "reason": "The form has no question for this column.",
                })
        location = {n for n, q in questions.items() if _is_location(q)}
        moved = [c["column"] for c in spec["columns"]
                 if c["question"] in location]
        spec["columns"] = [c for c in spec["columns"]
                           if c["question"] in questions
                           and c["question"] not in location]
        sheet = sheets.get(spec["sheet"], {})
        fed = {c["question"]: c["column"] for c in spec["columns"]}
        spec["value_maps"] = [
            vm for vm in spec["value_maps"]
            if "values" in sheet.get(fed.get(vm["question"]), {})
        ]
        for name, column in fed.items():
            q = questions[name]
            if q["type"] in ("option", "multiple_option") and \
                    "values" not in sheet.get(column, {}):
                q.update(type="input", option=[])
        if form["type"] != "registration" or \
                spec["administration_columns"]:
            continue
        spec["administration_columns"] = list(dict.fromkeys(moved))
        if spec["administration_columns"] and not source["columns"]:
            source.update(sheet=spec["sheet"],
                          columns=spec["administration_columns"])
    for spec in proposal["data"]:
        used = set(
            spec["key_columns"] + spec["parent_key_columns"]
            + spec["administration_columns"]
            + [c for c in (spec["geo"] or {}).values() if c]
            + [c["column"] for c in spec["columns"]]
        )
        spec["unmapped_columns"] = [
            c for c in spec["unmapped_columns"] if c["column"] not in used
        ]
