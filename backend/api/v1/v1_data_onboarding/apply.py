"""Check and apply a Proposal: the boundary the Apply job calls.

apply_proposal adds levels and units, creates and publishes the forms
(all in one transaction), then loads the rows best-effort as approved
data. Row rules are ported from #462's mis.py. Report reasons name
columns and questions, never cell values.
"""
import datetime
import re
import uuid

from django.conf import settings
from django.db import transaction
from django_q.tasks import async_task

from api.v1.v1_data.functions import answer_fields
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_data_onboarding.profile import OnboardingError, read_sheets
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.functions import (
    create_published_version,
    import_form_definition,
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import UserForms
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_visualization.functions import refresh_materialized_data
from utils.custom_generator import generate_sqlite

ONBOARDING_NS = uuid.UUID("6f1c3b7e-0d55-4b8e-9a51-5a0f3f6c2d11")


def _norm(v):
    return " ".join(str(v).split())


def _fold(v):
    return _norm(v).casefold()


def _text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return _norm(v)


def _lookup(pairs, raw):
    """pairs: {folded raw: target}. Returns raw when nothing matches."""
    return pairs.get(_fold(raw), raw)


def _to_number(v):
    if isinstance(v, (int, float)):
        return v
    s = re.sub(r"^[^\d\-.]+|[^\d.]+$", "", str(v).strip().replace(",", ""))
    try:
        f = float(s)
    except ValueError:
        raise ValueError("Not a number.") from None
    return int(f) if f.is_integer() else f


def _to_date(v, fmt):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime("%Y-%m-%d")
    s = _norm(v)
    try:
        if fmt:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?", s)
        if m:
            return datetime.date(*map(int, m.groups())).strftime("%Y-%m-%d")
    except ValueError:
        pass
    if fmt:
        raise ValueError("Not a date in the stated format.")
    raise ValueError("Not an ISO date, and the Proposal states no format.")


def _to_geo(v):
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(v))
    if len(nums) < 2:
        raise ValueError("Not a latitude and longitude.")
    lat, lng = float(nums[0]), float(nums[1])
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("Latitude or longitude is out of range.")
    return [lat, lng]


def _match_option(options, value_map, raw):
    """Return the stored option value for a raw cell."""
    label = _fold(_lookup(value_map, raw))
    if label not in options:
        raise ValueError("Not one of the options.")
    return options[label]


# --------------------------------------------------------- administration

def _admin_index(tenant):
    """{tuple of folded names below the root: Administration}."""
    admins = list(Administration.objects.filter(tenant=tenant))
    by_id = {a.id: a for a in admins}
    index = {}
    for a in admins:
        ids = [int(i) for i in (a.path or "").split(".") if i]
        names = [by_id[i].name for i in ids[1:]] + ([a.name] if ids else [])
        index[tuple(_fold(n) for n in names)] = a
    return index


def check_hierarchy(proposal, tenant, user):
    """Why the Proposal may not add its levels here, or None."""
    wanted = len(proposal["administration"]["levels"])
    if wanted <= Levels.objects.filter(tenant=tenant).count():
        return None
    if not user.is_superuser:
        return "Only a super admin can add administration levels."
    if Administration.objects.filter(
        tenant=tenant, parent__isnull=False
    ).exists():
        return (
            "Levels cannot be added: the administration tree already has"
            " units below the root."
        )
    return None


def _scope(user):
    """Ids of the units whose subtrees the user may onboard; None: all."""
    if user.is_superuser:
        return None
    return set(user.user_user_role.filter(
        role__role_role_feature_access__type=FeatureTypes.data_onboarding,
        role__role_role_feature_access__access=(
            FeatureAccessTypes.data_onboard
        ),
    ).values_list("administration_id", flat=True))


def _in_scope(unit, scope):
    ids = [unit.id] + [int(i) for i in (unit.path or "").split(".") if i]
    return scope is None or not scope.isdisjoint(ids)


class _Places:
    """Where location cells land in the tree, resolutions applied.

    Resolutions (DataOnboarding.resolutions, never in the Proposal):
    levels {form key: depth of its first location column}, parents
    [{name, parent: unit id}] for a name under several parents, aliases
    [{from, to}] and new_units [{name, match}] for near-matches.
    """

    def __init__(self, proposal, index, resolutions=None):
        r = resolutions or {}
        self.aliases = {
            _fold(a["from"]): a["to"]
            for a in proposal["administration"]["aliases"]
            + r.get("aliases", [])
        }
        self.starts = r.get("levels", {})
        self.parents = {_fold(p["name"]): p["parent"]
                        for p in r.get("parents", [])}
        self.new_units = {(_fold(u["name"]), _fold(u["match"]))
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
        return [_norm(_lookup(self.aliases, _text(c))) for c in cells]

    def path(self, cells, start):
        """Names from depth 1, or None when the top name can't be placed.

        Columns starting below depth 1 borrow the path above from the
        unit their top name names (as folded names: those units exist).
        """
        names = self.cells(cells)
        if start == 1 or not names:
            return names
        found = self.named.get((start, _fold(names[0])), [])
        if len(found) > 1:
            parent = self.parents.get(_fold(names[0]))
            found = [(k, u) for k, u in found if u.parent_id == parent]
        if len(found) != 1:
            return None
        return list(found[0][0]) + names[1:]


def _add_administration(admin, sheets, tenant, index, scope, places,
                        start=1):
    paths = [places.cells(u) for u in admin["units"]]
    source = admin["source"]
    if source["columns"]:
        df = sheets[source["sheet"]]
        for _, row in df.iterrows():
            cells = [row[c] for c in source["columns"]]
            if all(c is not None for c in cells):
                path = places.path(cells, start)
                if path:
                    paths.append(path)

    levels = list(Levels.objects.filter(tenant=tenant).order_by("level"))
    # check_hierarchy has allowed any levels beyond the existing ones.
    for depth, name in enumerate(admin["levels"]):
        if depth >= len(levels):
            levels.append(Levels.objects.create(
                tenant=tenant, name=name, level=depth
            ))

    for path in sorted(paths, key=len):
        for depth in range(1, len(path) + 1):
            key = tuple(_fold(n) for n in path[:depth])
            if key in index:
                continue
            if not _in_scope(index[key[:-1]], scope):
                break  # its rows are reported as outside the subtree
            if depth >= len(levels):
                raise OnboardingError(
                    "The locations go deeper than the administration levels."
                )
            index[key] = Administration.objects.create(
                parent=index[key[:-1]], level=levels[depth],
                name=path[depth - 1], tenant=tenant,
            )


# ------------------------------------------------------------------ forms

def _create_forms(forms, user):
    created = {}
    ordered = sorted(forms, key=lambda f: f["type"] == "monitoring")
    for spec in ordered:
        norm = normalize_form_definition(spec)
        errors = [
            i for i in validate_form_definition(norm) if i["level"] == "error"
        ]
        if errors:
            raise OnboardingError(
                f"Form '{spec['name']}' is not valid: {errors[0]['message']}"
            )
        parent = created.get(spec["parent"])
        form, _ = import_form_definition(
            norm, user, mode="create_copy",
            parent_id=parent.id if parent else None,
        )
        create_published_version(form, user, activate=True)
        form.refresh_from_db()
        UserForms.objects.get_or_create(user=user, form=form)
        created[spec["key"]] = form
    return created


# ------------------------------------------------------------------- rows

class _Rows:
    def __init__(self, form, spec, places, index, user, scope=None,
                 parents=None):
        self.form, self.spec, self.parents = form, spec, parents
        self.records = {}  # key: FormData, for monitoring rows to find
        self.places, self.index, self.user = places, index, user
        self.scope = scope
        self.questions = list(
            form.form_questions.select_related("question_group")
            .prefetch_related("options")
            .order_by("question_group__order", "order")
        )
        self.options = {
            q.id: {
                **{_fold(o.label): o.value for o in q.options.all()},
                **{_fold(o.value): o.value for o in q.options.all()},
            }
            for q in self.questions
        }
        self.columns = {c["question"]: c["column"] for c in spec["columns"]}
        self.value_maps = {
            m["question"]: {_fold(v["raw"]): v["label"] for v in m["values"]}
            for m in spec["value_maps"]
        }
        self.issues = []
        self.loaded = 0
        self.seen = set()

    def issue(self, line, question, kind, reason):
        self.issues.append({
            "sheet": self.spec["sheet"], "row": line,
            "question": question, "kind": kind, "reason": reason,
        })

    def convert(self, q, raw):
        t = q.type
        vmap = self.value_maps.get(q.name, {})
        if t == QuestionTypes.number:
            return _to_number(raw)
        if t == QuestionTypes.date:
            return _to_date(raw, self.spec["date_format"])
        if t == QuestionTypes.geo:
            return _to_geo(raw)
        if t == QuestionTypes.option:
            return [_match_option(self.options[q.id], vmap, _text(raw))]
        if t == QuestionTypes.multiple_option:
            sep = self.spec["multi_separator"] or r"[;,|/]"
            parts = [p for p in re.split(sep, _text(raw)) if p.strip()]
            return sorted({
                _match_option(self.options[q.id], vmap, p) for p in parts
            })
        return _text(raw)

    def raw(self, q, row):
        """The cell feeding q: None if blank, False if nothing feeds it."""
        geo = self.spec["geo"]
        if q.type == QuestionTypes.geo and geo:
            if geo["column"]:
                return row[geo["column"]]
            if row[geo["lat"]] is None:
                return None
            return f"{_text(row[geo['lat']])},{_text(row[geo['lng']])}"
        column = self.columns.get(q.name)
        if not column:
            return False
        value = row[column]
        if value is not None and not _norm(_lookup(
            self.value_maps.get(q.name, {}), _text(value)
        )):
            return None  # blank, or a value mapped to blank
        return value

    def location(self, row):
        cells = [row[c] for c in self.spec["administration_columns"]]
        if any(c is None for c in cells):
            raise ValueError("Location is blank.")
        path = self.places.path(cells, self.places.start(self.spec))
        if path is None:
            raise ValueError("Location is not in the administration tree.")
        key = tuple(_fold(n) for n in path)
        known = next(key[:n] for n in range(len(key), -1, -1)
                     if key[:n] in self.index)
        if not _in_scope(self.index[known], self.scope):
            raise ValueError("Location is outside your administration area.")
        if known != key:
            raise ValueError("Location is not in the administration tree.")
        return self.index[key]

    def load(self, line, row):
        cells = [row[c] for c in self.spec["key_columns"]]
        if any(c is None for c in cells):
            return self.issue(line, None, "skipped", "Key column is blank.")
        key = "|".join(_text(c) for c in cells)
        parent = None
        if self.parents is not None:
            cells = [row[c] for c in self.spec["parent_key_columns"]]
            if any(c is None for c in cells):
                return self.issue(line, None, "skipped",
                                  "Parent key column is blank.")
            parent = self.parents.get("|".join(_text(c) for c in cells))
            if not parent:
                return self.issue(line, None, "skipped",
                                  "No registration record has this key.")
        if key in self.seen:
            return self.issue(
                line, None, "skipped", "Repeated key; an earlier row loaded."
            )

        missing, warnings, values = [], [], []
        administration = geo = None
        for q in self.questions:
            if q.type == QuestionTypes.cascade and \
                    (q.extra or {}).get("type") == "administration":
                try:
                    administration = self.location(row)
                    values.append((q, administration.id))
                except ValueError as exc:
                    missing.append((q.name, str(exc)))
                continue
            raw = self.raw(q, row)
            if raw is False or raw is None:
                if q.required:
                    missing.append((q.name, "Required answer is blank."
                                    if raw is None else
                                    "No column feeds this required question."))
                continue
            try:
                value = self.convert(q, raw)
            except ValueError as exc:
                (missing if q.required else warnings).append(
                    (q.name, str(exc))
                )
                continue
            if q.type == QuestionTypes.geo:
                geo = value
            values.append((q, value))

        if missing:
            for name, reason in missing:
                self.issue(line, name, "skipped", reason)
            return
        for name, reason in warnings:
            self.issue(line, name, "warning", reason)

        name = " - ".join(
            str(administration.name if q.type == QuestionTypes.cascade
                else v)
            for q, v in values if q.meta and q.type != QuestionTypes.geo
        ) or key
        record_uuid = str(uuid.uuid5(ONBOARDING_NS, f"{self.form.id}/{key}"))
        if parent:
            # A visit takes its identity and location from its parent.
            name, administration, geo = (
                parent.name, parent.administration, parent.geo
            )
            record_uuid = parent.uuid
        data = FormData.objects.create(
            name=name, form=self.form, administration=administration,
            geo=geo, created_by=self.user, is_pending=False,
            uuid=record_uuid, parent=parent,
            published_version=self.form.active_version,
        )
        self.records[key] = data
        answers = []
        for q, value in values:
            a_name, a_value, a_options = answer_fields(q, value)
            answers.append(Answers(
                data=data, question=q, name=a_name, value=a_value,
                options=a_options, created_by=self.user,
            ))
        Answers.objects.bulk_create(answers)
        if not settings.TEST_ENV and not self.form.parent:
            data.save_to_file
        self.seen.add(key)
        self.loaded += 1


def _unblocked(proposal, blocked, chosen):
    """The Proposal cut down to the chosen forms that are not blocked."""
    skip = {b["form"] for b in blocked}
    keys = {
        f["key"] for f in proposal["forms"]
        if f["key"] not in skip and (chosen is None or f["key"] in chosen)
    }
    admin = proposal["administration"]
    loaders = {
        d["form"] for d in proposal["data"]
        if d["sheet"] == admin["source"]["sheet"]
    }
    if loaders and not loaders & keys:
        # The units belong to forms that are not applied.
        admin = {**admin, "units": [],
                 "source": {"sheet": None, "columns": []}}
    return {
        **proposal, "administration": admin,
        "forms": [f for f in proposal["forms"] if f["key"] in keys],
        "data": [d for d in proposal["data"] if d["form"] in keys],
    }


def apply_proposal(proposal, path, file_name, tenant, user, forms=None,
                   resolutions=None):
    """Apply a Proposal to the tenant and return the Onboarding Report.

    The ambiguity checks run again first: only the chosen forms (all
    when None) that are not blocked now are applied; the blocked ones
    are reported. Levels, units and forms are all-or-nothing: on any
    error none exist and the error propagates. Rows then load one by
    one; a bad row is skipped and reported, never fatal.
    """
    # Imported here: ambiguity reuses this module's helpers.
    from api.v1.v1_data_onboarding.ambiguity import blocked_forms

    sheets = read_sheets(path, file_name)
    blocked = blocked_forms(proposal, sheets, tenant, user, resolutions)
    proposal = _unblocked(proposal, blocked, forms)
    index = _admin_index(tenant)
    before = len(index)
    scope = _scope(user)
    with transaction.atomic():
        refusal = check_hierarchy(proposal, tenant, user)
        if refusal:
            raise OnboardingError(refusal)
        places = _Places(proposal, index, resolutions)
        admin = proposal["administration"]
        source = next((d for d in proposal["data"]
                       if d["sheet"] == admin["source"]["sheet"]), None)
        _add_administration(
            admin, sheets, tenant, index, scope, places,
            places.start(source) if source else 1,
        )
        forms = _create_forms(proposal["forms"], user)
    if len(index) > before:
        generate_sqlite(Administration, tenant=tenant)
    async_task("api.v1.v1_forms.tasks.refresh_form_config")

    report = {"forms": [], "issues": [], "blocked": blocked}
    records = {}  # form key: {row key: FormData}
    # Registration rows first, so visits can find their parent records.
    parent_of = {f["key"]: f["parent"] for f in proposal["forms"]}
    for spec in sorted(proposal["data"],
                       key=lambda s: parent_of[s["form"]] is not None):
        form = forms[spec["form"]]
        parents = None
        if parent_of[spec["form"]]:
            parents = records.get(parent_of[spec["form"]], {})
        rows = _Rows(form, spec, places, index, user, scope, parents)
        records[spec["form"]] = rows.records
        for i, row in sheets[spec["sheet"]].iterrows():
            rows.load(i + 2, row)  # i is 0-based after a header row
        report["forms"].append({
            "key": spec["form"], "name": form.name, "form": form.id,
            "loaded": rows.loaded,
        })
        report["issues"] += rows.issues
    refresh_materialized_data()
    return report
