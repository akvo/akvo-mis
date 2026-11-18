"""Which forms of a Proposal are blocked, and why.

blocked_forms runs on every draft and again at Apply, against the file
and the tenant's tree as they are then. A check takes (form, data spec
or None, context) and returns causes {kind, reason, ...}; add a check
to CHECKS to block forms for a new reason. Proposal suggestions (column
order, aliases, units) are the checks' input, never their result.

Findings hold names from the file, so they are stored beside the
Proposal, never in it: the Proposal goes back to OpenAI.
"""
import re

from api.v1.v1_data_onboarding.apply import (
    _admin_index,
    _fold,
    _in_scope,
    _lookup,
    _norm,
    _scope,
    _text,
)
from api.v1.v1_profile.models import Levels


class _Context:
    def __init__(self, proposal, sheets, tenant, user):
        self.proposal, self.sheets = proposal, sheets
        admin = proposal["administration"]
        self.aliases = {_fold(a["from"]): a["to"] for a in admin["aliases"]}
        self.index = _admin_index(tenant)
        levels = list(Levels.objects.filter(tenant=tenant).order_by("level"))
        self.level_names = [lv.name for lv in levels]
        # check_hierarchy refuses a Proposal whose new levels can't be added.
        self.depth = max(len(levels), len(admin["levels"])) - 1
        self.scope = _scope(user)
        # {depth: {folded name: number of parents}}, {parent key: names}
        self.by_depth, self.children = {}, {}
        for key, unit in self.index.items():
            if key:
                names = self.by_depth.setdefault(len(key), {})
                names[key[-1]] = names.get(key[-1], 0) + 1
                self.children.setdefault(key[:-1], []).append(unit.name)

    def paths(self, spec):
        """Location paths of the spec's rows, aliases applied."""
        columns = spec["administration_columns"]
        paths = set()
        for cells in self.sheets[spec["sheet"]][columns].itertuples(
            index=False
        ):
            if all(c is not None for c in cells):
                paths.add(tuple(
                    _norm(_lookup(self.aliases, _text(c))) for c in cells
                ))
        return paths

    def depths_of(self, names):
        folded = {_fold(n) for n in names}
        return {d for d, known in self.by_depth.items() if folded & set(known)}

    def level_name(self, depth):
        if depth < len(self.level_names):
            return f"'{self.level_names[depth]}'"
        return f"number {depth}"


def _cause(kind, reason, **extra):
    return {"kind": kind, "reason": reason, **extra}


def _no_location(form, spec, ctx):
    if form["type"] == "registration" and spec and \
            not spec["administration_columns"]:
        return [_cause("no_location",
                       "The sheet has no location column, so its records"
                       " cannot be placed in the administration tree.")]
    return []


def _level_mapping(form, spec, ctx):
    columns = spec["administration_columns"] if spec else []
    causes = []
    if len(columns) > ctx.depth:
        causes.append(_cause(
            "level_mapping",
            f"There are {len(columns)} location columns but only"
            f" {ctx.depth} levels below the root.",
        ))
    paths = ctx.paths(spec) if columns else set()
    for i, column in enumerate(columns):
        found = ctx.depths_of({p[i] for p in paths})
        if found and i + 1 not in found:
            causes.append(_cause(
                "level_mapping",
                f"Column '{column}' is read as level"
                f" {ctx.level_name(i + 1)}, but its names are units of"
                f" level {ctx.level_name(min(found))}.",
                column=column,
            ))
    return causes


def _shared_name(form, spec, ctx):
    """The top column names units of a deeper level: no parent column."""
    if not spec or not spec["administration_columns"]:
        return []
    names = {p[0] for p in ctx.paths(spec)}
    found = ctx.depths_of(names)
    if len(found) != 1 or 1 in found:
        return []
    known = ctx.by_depth[found.pop()]
    shared = sorted(n for n in names if known.get(_fold(n), 0) > 1)
    if not shared:
        return []
    return [_cause(
        "shared_name",
        f"Some names in column '{spec['administration_columns'][0]}' exist"
        " under several parents, and no column gives the parent.",
        units=shared,
    )]


def _squash(name):
    return re.sub(r"[\W_]+", "", name.casefold())


def _distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(
                row[j] + 1, row[j - 1] + 1, prev + (ca != cb)
            )
    return row[-1]


def _near(a, b):
    a, b = _squash(a), _squash(b)
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return _distance(a, b) <= (1 if max(len(a), len(b)) < 8 else 2)


def _near_match(form, spec, ctx):
    """A unit Apply would add that looks like an existing sibling."""
    if not spec or not spec["administration_columns"]:
        return []
    paths = ctx.paths(spec)
    admin = ctx.proposal["administration"]
    if spec["sheet"] == admin["source"]["sheet"]:
        # Apply adds the proposed units with this sheet's units.
        paths |= {
            tuple(_norm(_lookup(ctx.aliases, n)) for n in u)
            for u in admin["units"]
        }
    matches = set()
    for path in paths:
        key = tuple(_fold(n) for n in path)
        depth = next(
            (d for d in range(1, len(key) + 1) if key[:d] not in ctx.index),
            None,
        )
        if depth is None or depth > ctx.depth:
            continue
        if not _in_scope(ctx.index[key[:depth - 1]], ctx.scope):
            continue  # outside the subtree: skipped, not ambiguous
        name = path[depth - 1]
        for sibling in ctx.children.get(key[:depth - 1], []):
            if _near(name, sibling):
                matches.add((name, sibling))
    if not matches:
        return []
    return [_cause(
        "near_match",
        "Some new units are spelled like existing units, and would"
        " duplicate them.",
        units=[{"name": n, "match": m} for n, m in sorted(matches)],
    )]


CHECKS = [_level_mapping, _shared_name, _near_match, _no_location]


def blocked_forms(proposal, sheets, tenant, user):
    """[{form, name, causes}] for each form that cannot be applied."""
    ctx = _Context(proposal, sheets, tenant, user)
    specs = {d["form"]: d for d in proposal["data"]}
    blocked = {}
    for form in proposal["forms"]:
        spec = specs.get(form["key"])
        causes = [c for check in CHECKS for c in check(form, spec, ctx)]
        if causes:
            blocked[form["key"]] = causes
    for form in proposal["forms"]:
        if form["parent"] in blocked:
            blocked.setdefault(form["key"], []).append(_cause(
                "parent_blocked", "Its registration form is blocked.",
            ))
    return [
        {"form": f["key"], "name": f["name"], "causes": blocked[f["key"]]}
        for f in proposal["forms"] if f["key"] in blocked
    ]
