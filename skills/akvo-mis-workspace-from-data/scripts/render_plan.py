#!/usr/bin/env python
"""Check plan.json against its data files and render it for a human.

    python render_plan.py plan.json [-o plan.md]

Prints problems first (unknown columns, values that match no option,
administration paths with blanks, monitoring rows with no registration),
then writes the plan as plain-language tables: the workspace, the
administration tree, every form question by question, and how each
spreadsheet column maps onto a question. The user approves THIS document,
never the JSON.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mis import (blank, mapped_blank, match_option, norm, plan_questions,  # noqa: E402
                 read_table, row_key, to_date, to_geo, to_number)

TYPE_WORDS = {
    "input": "short text", "text": "long text", "number": "number",
    "date": "date", "option": "pick one", "multiple_option": "pick several",
    "geo": "GPS point", "administration": "location (administration)",
    "photo": "photo", "signature": "signature", "attachment": "file",
}


class P:
    def __init__(self, plan_path):
        self.plan_path = os.path.abspath(plan_path)
        import json
        with open(self.plan_path) as f:
            self.plan = json.load(f)
        self.plan_dir = os.path.dirname(self.plan_path)

    def path(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.plan_dir, rel)


def check(ctx):
    plan, problems, stats = ctx.plan, [], {}
    forms = {f["key"]: f for f in plan["forms"]}
    names = set()
    for f in plan["forms"]:
        if f["type"] == "monitoring" and f.get("parent") not in forms:
            problems.append(f"form {f['key']}: parent '{f.get('parent')}' "
                            f"is not a form in the plan")
        qs = plan_questions(f)
        admin_q = [q for q in qs if q["type"] == "administration"]
        if f["type"] == "registration" and len(admin_q) != 1:
            problems.append(f"form {f['key']}: a registration form needs "
                            f"exactly one administration question")
        if f["type"] == "registration" and not any(q.get("meta")
                                                   for q in qs):
            problems.append(f"form {f['key']}: mark the naming question(s) "
                            f"meta: true so datapoints get readable names")
        local = set()
        for q in qs:
            if q["name"] in local:
                problems.append(f"form {f['key']}: duplicate question "
                                f"name {q['name']}")
            local.add(q["name"])
            if q["type"] in ("option", "multiple_option") and \
                    not q.get("options"):
                problems.append(f"{f['key']}.{q['name']}: no options")
            dep = q.get("depends_on")
            if dep and dep["question"] not in local:
                problems.append(f"{f['key']}.{q['name']}: depends on "
                                f"'{dep['question']}' which must come "
                                f"earlier in the form")
        if f["name"].casefold() in names:
            problems.append(f"two forms named '{f['name']}'")
        names.add(f["name"].casefold())
    reg_keys = {}
    ordered = sorted(plan.get("data", []),
                     key=lambda d: forms[d["form"]]["type"] == "monitoring")
    aliases = plan["administration"].get("aliases", {})
    for spec in ordered:
        f = forms.get(spec["form"])
        if not f:
            problems.append(f"data for unknown form {spec['form']}")
            continue
        try:
            df = read_table(ctx, spec)
        except Exception as e:  # noqa: BLE001 - report any read failure
            problems.append(f"{spec['form']}: cannot read {spec['file']}: "
                            f"{e}")
            continue
        cols = set(df.columns)
        want = list(spec.get("columns", {}).values())
        want += spec.get("key_columns", []) + \
            spec.get("administration_columns", [])
        g = spec.get("geo") or {}
        want += [g[k] for k in ("lat", "lng", "column") if k in g]
        if spec.get("parent"):
            want += spec["parent"]["key_columns"]
        for c in want:
            if c not in cols:
                problems.append(f"{spec['form']}: column '{c}' not in "
                                f"{spec['file']} (has: {sorted(cols)})")
        if any(c not in cols for c in want):
            continue
        qs = {q["name"]: q for q in plan_questions(f)}
        bad, blanks, keys, orphans = {}, 0, set(), 0
        dup = 0
        for _, row in df.iterrows():
            for qn, col in spec.get("columns", {}).items():
                q = qs.get(qn)
                if q is None:
                    problems.append(f"{spec['form']}: columns maps unknown "
                                    f"question '{qn}'")
                    continue
                v = row[col]
                if blank(v) or mapped_blank(spec, qn, v):
                    continue
                try:
                    vm = spec.get("value_maps", {}).get(qn, {})
                    if q["type"] == "number":
                        to_number(v)
                    elif q["type"] == "date":
                        to_date(v, spec.get("date_format"))
                    elif q["type"] == "geo":
                        to_geo(v)
                    elif q["type"] == "option":
                        match_option(q, v, vm)
                    elif q["type"] == "multiple_option":
                        import re
                        for p in re.split(spec.get("multi_separator",
                                                   r"[;,|/]"), str(v)):
                            if p.strip():
                                match_option(q, p, vm)
                except (ValueError, TypeError) as e:
                    msg = norm(v)
                    if "date_format" in str(e):
                        msg = f"{msg} (ambiguous: set date_format)"
                    bad.setdefault(qn, set()).add(msg)
            if spec.get("administration_columns") and any(
                    blank(row[c]) for c in spec["administration_columns"]):
                blanks += 1
            k = row_key(row, spec.get("key_columns") or [])
            if spec.get("key_columns"):
                if k in keys:
                    dup += 1
                keys.add(k)
            if spec.get("parent"):
                pk = row_key(row, spec["parent"]["key_columns"])
                if pk not in reg_keys.get(spec["parent"]["form"], set()):
                    orphans += 1
        if f["type"] == "registration":
            reg_keys[f["key"]] = keys
        for qn, vals in bad.items():
            problems.append(f"{spec['form']}.{qn}: values that fit no "
                            f"option/format: {sorted(vals)[:10]}")
        if blanks:
            problems.append(f"{spec['form']}: {blanks} rows have a blank "
                            f"administration column and will be skipped")
        if dup:
            problems.append(f"{spec['form']}: {dup} rows repeat a key "
                            f"{spec.get('key_columns')} — only the first "
                            f"is loaded")
        if orphans:
            problems.append(f"{spec['form']}: {orphans} rows point at no "
                            f"registration row and will be skipped")
        stats[spec["form"]] = len(df)
    del aliases
    return problems, stats


def render(ctx, stats):
    plan = ctx.plan
    ws, adm = plan["workspace"], plan["administration"]
    out = [f"# MIS setup plan: {ws['subdomain']}.{ws['base_domain']}", ""]
    out += ["## Workspace", "",
            f"- Address: {ws.get('scheme', 'https')}://{ws['subdomain']}."
            f"{ws['base_domain']}",
            f"- Admin account: {ws['email']} (a temporary password is "
            f"generated; the activation link arrives by email)", ""]
    out += ["## Administration", "",
            "Levels, top to bottom: " + " > ".join(adm["levels"]), ""]
    try:
        from mis import admin_units
        units = admin_units(ctx)
    except Exception:  # noqa: BLE001
        units = [tuple(u) for u in adm.get("units", [])]
    out.append(f"- **{adm['root']}** ({adm['levels'][0]})")
    for u in sorted(units, key=lambda p: [x.casefold() for x in p]):
        lvl = adm["levels"][len(u)] if len(u) < len(adm["levels"]) else "?"
        out.append("  " * len(u) + f"- {u[-1]} ({lvl})")
    out.append("")
    if adm.get("aliases"):
        out += ["Spelling fixes applied to the data: " + ", ".join(
            f"'{k}' → '{v}'" for k, v in adm["aliases"].items()), ""]
    for f in plan["forms"]:
        kind = "Registration form" if f["type"] == "registration" else \
            f"Monitoring form (repeated visits to a {f['parent']} record)"
        out += [f"## {f['name']}", "", f"*{kind}.* {f.get('description', '')}",
                ""]
        spec = next((d for d in plan.get("data", [])
                     if d["form"] == f["key"]), {})
        src = {q: c for q, c in spec.get("columns", {}).items()}
        for g in f["groups"]:
            out += [f"**{g['label']}**", "",
                    "| # | Question | Answer type | Required | Choices / rule "
                    "| Shown when | From column |",
                    "|---|---|---|---|---|---|---|"]
            for i, q in enumerate(g["questions"], 1):
                rule = ", ".join(q.get("options", []))
                if q["type"] == "number":
                    rng = [f"min {q['min']}" if q.get("min") is not None
                           else "", f"max {q['max']}"
                           if q.get("max") is not None else "",
                           "decimals" if q.get("decimal", True)
                           else "whole numbers"]
                    rule = ", ".join(x for x in rng if x)
                dep = q.get("depends_on")
                labels = {x["name"]: x["label"] for x in plan_questions(f)}
                shown = f"{labels.get(dep['question'], dep['question'])} = " \
                    f"{' or '.join(dep['values'])}" if dep else ""
                col = src.get(q["name"], "")
                if q["type"] == "administration":
                    col = " > ".join(spec.get("administration_columns", []))
                if q["type"] == "geo" and spec.get("geo"):
                    g2 = spec["geo"]
                    col = f"{g2['lat']} + {g2['lng']}" if "lat" in g2 \
                        else g2["column"]
                label = q["label"] + (" ★" if q.get("meta") else "")
                out.append(f"| {i} | {label} | {TYPE_WORDS[q['type']]} | "
                           f"{'yes' if q.get('required') else ''} | {rule} | "
                           f"{shown} | {col} |")
            out.append("")
        out += ["★ = used to name each record.", ""]
    out += ["## Data to load", ""]
    for d in plan.get("data", []):
        n = stats.get(d["form"], "?")
        link = f", linked to {d['parent']['form']} by " \
            f"{' + '.join(d['parent']['key_columns'])}" if d.get("parent") \
            else ""
        out.append(f"- {d['form']}: {n} rows from `{d['file']}`"
                   f"{' / ' + d['sheet'] if d.get('sheet') else ''}{link}")
        unused = d.get("unmapped_columns")
        if unused:
            out.append(f"  - not loaded: {', '.join(unused)}")
    if plan.get("notes"):
        out += ["", "## Decisions and caveats", ""]
        out += [f"- {n}" for n in plan["notes"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    ctx = P(a.plan)
    problems, stats = check(ctx)
    if problems:
        print("PROBLEMS (fix the plan or the data, then re-run):")
        for p in problems:
            print(f"  - {p}")
    else:
        print("plan checks: OK")
    md = render(ctx, stats)
    out = a.out or os.path.join(ctx.plan_dir, "plan.md")
    with open(out, "w") as f:
        f.write(md)
    print(f"wrote {out}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
