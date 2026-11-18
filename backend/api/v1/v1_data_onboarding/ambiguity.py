"""Which forms of a Proposal are blocked, and why.

blocked_forms runs on every draft and again at Apply, against the file
and the tenant's tree as they are then. A check takes (form, data spec
or None, context) and returns causes {kind, reason, ...}; add a check
to CHECKS to block forms for a new reason. Proposal suggestions (column
order, aliases) are the checks' input, never their result.

Findings hold names from the file, so they are stored beside the
Proposal, never in it: the Proposal goes back to OpenAI.
"""
import re

from api.v1.v1_data_onboarding.places import (
    Places,
    admin_index,
    fold,
    in_scope,
    user_scope,
)
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Levels


class _Context:
    def __init__(self, proposal, sheets, tenant, user, resolutions):
        self.proposal, self.sheets = proposal, sheets
        admin = proposal["administration"]
        self.index = admin_index(tenant)
        self.places = Places(proposal, self.index, resolutions)
        levels = list(Levels.objects.filter(tenant=tenant).order_by("level"))
        self.level_names = [lv.name for lv in levels]
        # check_hierarchy refuses a Proposal whose new levels can't be added.
        self.depth = max(len(levels), len(admin["levels"])) - 1
        self.scope = user_scope(user)
        # The default manager leaves archived forms out: they never clash.
        self.form_names = {
            fold(n) for n in
            Forms.objects.filter(tenant=tenant).values_list("name", flat=True)
        }
        # {depth: {folded name: number of parents}}, {parent key: names}
        self.by_depth, self.children = {}, {}
        for key, unit in self.index.items():
            if key:
                names = self.by_depth.setdefault(len(key), {})
                names[key[-1]] = names.get(key[-1], 0) + 1
                self.children.setdefault(key[:-1], []).append(unit.name)

    def rows(self, spec):
        columns = spec["administration_columns"]
        return {
            cells for cells in self.sheets[spec["sheet"]][columns]
            .itertuples(index=False) if all(c is not None for c in cells)
        }

    def paths(self, spec):
        """The location cells of the spec's rows, aliases applied."""
        return {tuple(self.places.cells(c)) for c in self.rows(spec)}

    def full_paths(self, spec):
        """As paths, from depth 1; rows that can't be placed left out."""
        start = self.places.start(spec)
        paths = (self.places.path(c, start) for c in self.rows(spec))
        return {tuple(p) for p in paths if p is not None}

    def depths_of(self, names):
        folded = {fold(n) for n in names}
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
    if not columns:
        return []
    start = ctx.places.start(spec)
    causes = []
    if start - 1 + len(columns) > ctx.depth:
        causes.append(_cause(
            "level_mapping",
            f"There are {len(columns)} location columns but only"
            f" {ctx.depth - start + 1} levels below the root"
            f"{'' if start == 1 else ' from the first column down'}.",
        ))
    paths = ctx.paths(spec)
    for i, column in enumerate(columns):
        found = ctx.depths_of({p[i] for p in paths})
        if found and start + i not in found:
            causes.append(_cause(
                "level_mapping",
                f"Column '{column}' is read as level"
                f" {ctx.level_name(start + i)}, but its names are units of"
                f" level {ctx.level_name(min(found))}.",
                column=column,
            ))
    return causes


def _shared_name(form, spec, ctx):
    """The top column names units of a deeper level: no parent column."""
    if not spec or not spec["administration_columns"]:
        return []
    names = {p[0] for p in ctx.paths(spec)}
    depth = ctx.places.start(spec)
    if depth == 1:
        found = ctx.depths_of(names)
        if len(found) != 1 or 1 in found:
            return []
        depth = found.pop()
    units = []
    for name in sorted(names):
        found = ctx.places.named.get((depth, fold(name)), [])
        chosen = ctx.places.parents.get(fold(name))
        if len(found) > 1 and chosen not in {u.parent_id for _, u in found}:
            units.append({"name": name, "parents": [
                {"id": u.parent_id, "name": " › ".join(
                    ctx.index[k[:i]].name for i in range(1, len(k))
                )}
                for k, u in found
            ]})
    if not units:
        return []
    return [_cause(
        "shared_name",
        f"Some names in column '{spec['administration_columns'][0]}' exist"
        " under several parents, and no column gives the parent.",
        units=units,
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
    paths = ctx.full_paths(spec)
    matches = set()
    for path in paths:
        key = tuple(fold(n) for n in path)
        depth = next(
            (d for d in range(1, len(key) + 1) if key[:d] not in ctx.index),
            None,
        )
        if depth is None or depth > ctx.depth:
            continue
        if not in_scope(ctx.index[key[:depth - 1]], ctx.scope):
            continue  # outside the subtree: skipped, not ambiguous
        name = path[depth - 1]
        confirmed = ctx.places.new_units
        for sibling in ctx.children.get(key[:depth - 1], []):
            if _near(name, sibling) and \
                    (fold(name), fold(sibling)) not in confirmed:
                matches.add((name, sibling))
    if not matches:
        return []
    return [_cause(
        "near_match",
        "Some new units are spelled like existing units, and would"
        " duplicate them.",
        units=[{"name": n, "match": m} for n, m in sorted(matches)],
    )]


def _name_clash(form, spec, ctx):
    if fold(form["name"]) not in ctx.form_names:
        return []
    return [_cause(
        "name_clash",
        f"An active form is already named '{form['name']}'. Rename this"
        " form, or archive the old one.",
    )]


CHECKS = [
    _level_mapping, _shared_name, _near_match, _no_location, _name_clash,
]


def blocked_forms(proposal, sheets, tenant, user, resolutions=None):
    """[{form, name, causes}] for each form that cannot be applied."""
    ctx = _Context(proposal, sheets, tenant, user, resolutions)
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
