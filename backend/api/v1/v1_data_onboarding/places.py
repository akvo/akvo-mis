"""Where file cells land in the tenant's tree.

Shared by the profile, Apply, the ambiguity checks and the edits: cell
text, the tree index, the importer's scope, and how location cells map
onto units with resolutions applied.
"""
import datetime

from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import Administration


def norm(v):
    return " ".join(str(v).split())


def fold(v):
    return norm(v).casefold()


def text(v):
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=" ").removesuffix(" 00:00:00")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return norm(v)


def lookup(pairs, raw):
    """pairs: {folded raw: target}. Returns raw when nothing matches."""
    return pairs.get(fold(raw), raw)


def admin_index(tenant):
    """{tuple of folded names below the root: Administration}."""
    admins = list(Administration.objects.filter(tenant=tenant))
    by_id = {a.id: a for a in admins}
    index = {}
    for a in admins:
        ids = [int(i) for i in (a.path or "").split(".") if i]
        names = [by_id[i].name for i in ids[1:]] + ([a.name] if ids else [])
        index[tuple(fold(n) for n in names)] = a
    return index


def user_scope(user):
    """Ids of the units whose subtrees the user may onboard; None: all."""
    if user.is_superuser:
        return None
    return set(user.user_user_role.filter(
        role__role_role_feature_access__type=FeatureTypes.data_onboarding,
        role__role_role_feature_access__access=(
            FeatureAccessTypes.data_onboard
        ),
    ).values_list("administration_id", flat=True))


def in_scope(unit, scope):
    ids = [unit.id] + [int(i) for i in (unit.path or "").split(".") if i]
    return scope is None or not scope.isdisjoint(ids)


def cut_forms(proposal, keys):
    """The Proposal with only the forms in keys and their data specs.

    The units go too when no kept form loads the sheet they come from.
    """
    admin = proposal["administration"]
    loaders = {
        d["form"] for d in proposal["data"]
        if d["sheet"] == admin["source"]["sheet"]
    }
    if loaders and not loaders & keys:
        admin = {**admin, "units": [],
                 "source": {"sheet": None, "columns": []}}
    return {
        **proposal, "administration": admin,
        "forms": [f for f in proposal["forms"] if f["key"] in keys],
        "data": [d for d in proposal["data"] if d["form"] in keys],
    }


class Places:
    """Where location cells land in the tree, resolutions applied.

    Resolutions (DataOnboarding.resolutions, never in the Proposal):
    levels {form key: depth of its first location column}, parents
    [{name, parent: unit id}] for a name under several parents, aliases
    [{from, to}] and new_units [{name, match}] for near-matches.
    """

    def __init__(self, proposal, index, resolutions=None):
        r = resolutions or {}
        self.aliases = {
            fold(a["from"]): a["to"]
            for a in proposal["administration"]["aliases"]
            + r.get("aliases", [])
        }
        self.starts = r.get("levels", {})
        self.parents = {fold(p["name"]): p["parent"]
                        for p in r.get("parents", [])}
        self.new_units = {(fold(u["name"]), fold(u["match"]))
                          for u in r.get("new_units", [])}
        self.index = index
        self.named = {}  # (depth, folded name): [(key, unit)]
        for key, unit in index.items():
            if key:
                self.named.setdefault((len(key), key[-1]), []).append(
                    (key, unit)
                )

    def start(self, spec):
        return self.starts.get(spec["form"], 1)

    def cells(self, cells):
        return [norm(lookup(self.aliases, text(c))) for c in cells]

    def path(self, cells, start):
        """Names from depth 1, or None when the top name can't be placed.

        Columns starting below depth 1 borrow the path above from the
        unit their top name names (as folded names: those units exist).
        """
        names = self.cells(cells)
        if start == 1 or not names:
            return names
        found = self.named.get((start, fold(names[0])), [])
        if len(found) > 1:
            parent = self.parents.get(fold(names[0]))
            found = [(k, u) for k, u in found if u.parent_id == parent]
        if len(found) != 1:
            return None
        return list(found[0][0]) + names[1:]

    def unit_paths(self, proposal, sheets):
        """Name paths of the units Apply adds: proposed, then the file's."""
        admin = proposal["administration"]
        paths = [self.cells(u) for u in admin["units"]]
        source = admin["source"]
        if not source["columns"]:
            return paths
        spec = next((d for d in proposal["data"]
                     if d["sheet"] == source["sheet"]), None)
        start = self.start(spec) if spec else 1
        for _, row in sheets[source["sheet"]].iterrows():
            cells = [row[c] for c in source["columns"]]
            if all(c is not None for c in cells):
                path = self.path(cells, start)
                if path:
                    paths.append(path)
        return paths
