"""Check and apply a Proposal: the boundary the Apply job calls.

apply_proposal adds levels and units, creates and publishes the forms
(all in one transaction), then loads the rows best-effort as approved
data. Row rules are ported from #462's mis.py. Report reasons name
columns and questions, never cell values.
"""
import datetime
import logging
import re
import uuid

from django.conf import settings
from django.db import transaction
from django_q.tasks import async_task

from api.v1.v1_data.functions import answer_fields
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_data_onboarding.ambiguity import blocked_forms
from api.v1.v1_data_onboarding.places import (
    Places,
    admin_index,
    cut_forms,
    fold,
    in_scope,
    lookup,
    norm,
    text,
    user_scope,
)
from api.v1.v1_data_onboarding.profile import OnboardingError, read_sheets
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.functions import (
    create_published_version,
    import_form_definition,
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import UserForms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_visualization.functions import refresh_materialized_data
from utils.custom_generator import generate_sqlite

logger = logging.getLogger(__name__)

ONBOARDING_NS = uuid.UUID("6f1c3b7e-0d55-4b8e-9a51-5a0f3f6c2d11")
ROW_FAILED = "This row could not be loaded."


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
    s = norm(v)
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
    label = fold(lookup(value_map, raw))
    if label not in options:
        raise ValueError("Not one of the options.")
    return options[label]


# --------------------------------------------------------- administration

def check_hierarchy(proposal, tenant, user):
    """Why the Proposal may not add its levels here, or None."""
    wanted = len(proposal["administration"]["levels"])
    if wanted <= Levels.objects.filter(tenant=tenant).count():
        return None
    if not user.is_superuser:
        return "Only a super admin can add administration levels."
    if Levels.objects.filter(tenant=tenant, level__gt=0).exists():
        return (
            "Levels cannot be added: the tenant already has levels below"
            " the root."
        )
    return None


def _add_administration(admin, paths, tenant, index, scope):
    levels = list(Levels.objects.filter(tenant=tenant).order_by("level"))
    # check_hierarchy has allowed any levels beyond the existing ones.
    for depth, name in enumerate(admin["levels"]):
        if depth >= len(levels):
            levels.append(Levels.objects.create(
                tenant=tenant, name=name, level=depth
            ))

    for path in sorted(paths, key=len):
        for depth in range(1, len(path) + 1):
            key = tuple(fold(n) for n in path[:depth])
            if key in index:
                continue
            if not in_scope(index[key[:-1]], scope):
                break  # its rows are reported as outside the subtree
            if depth >= len(levels):
                raise OnboardingError(
                    "The locations go deeper than the administration levels."
                )
            index[key] = Administration.objects.create(
                parent=index[key[:-1]], level=levels[depth],
                name=path[depth - 1], tenant=tenant,
            )


def planned_units(proposal, sheets, tenant, user, blocked,
                  resolutions=None):
    """The units Apply would add for user, for the review only.

    {"new": [path], "outside": [path]}: name paths from depth 1 of each
    unit Apply adds, and of each it leaves out as outside the user's
    subtree. They hold file values: never in the Proposal or Report.
    """
    proposal = _unblocked(proposal, blocked, None)
    index = admin_index(tenant)
    scope = user_scope(user)
    places = Places(proposal, index, resolutions)
    new, outside = {}, {}
    for path in places.unit_paths(proposal, sheets):
        key = tuple(fold(n) for n in path)
        known = next(n for n in range(len(key), -1, -1) if key[:n] in index)
        found = new if in_scope(index[key[:known]], scope) else outside
        for depth in range(known + 1, len(key) + 1):
            found.setdefault(key[:depth], path[:depth])
    return {"new": sorted(new.values()), "outside": sorted(outside.values())}


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
                **{fold(o.label): o.value for o in q.options.all()},
                **{fold(o.value): o.value for o in q.options.all()},
            }
            for q in self.questions
        }
        self.columns = {c["question"]: c["column"] for c in spec["columns"]}
        self.value_maps = {
            m["question"]: {fold(v["raw"]): v["label"] for v in m["values"]}
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
            return [_match_option(self.options[q.id], vmap, text(raw))]
        if t == QuestionTypes.multiple_option:
            # Each character of the separator splits, as a literal.
            seps = self.spec["multi_separator"] or ";,|/"
            parts = [p.strip() for p in
                     re.split(f"[{re.escape(seps)}]", text(raw))
                     if p.strip()]
            return sorted({
                _match_option(self.options[q.id], vmap, p) for p in parts
            })
        return text(raw)

    def raw(self, q, row):
        """The cell feeding q: None if blank, False if nothing feeds it."""
        geo = self.spec["geo"]
        if q.type == QuestionTypes.geo and geo:
            if geo["column"]:
                return row[geo["column"]]
            if row[geo["lat"]] is None:
                return None
            return f"{text(row[geo['lat']])},{text(row[geo['lng']])}"
        column = self.columns.get(q.name)
        if not column:
            return False
        value = row[column]
        if value is not None and not norm(lookup(
            self.value_maps.get(q.name, {}), text(value)
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
        key = tuple(fold(n) for n in path)
        known = next(key[:n] for n in range(len(key), -1, -1)
                     if key[:n] in self.index)
        if not in_scope(self.index[known], self.scope):
            raise ValueError("Location is outside your administration area.")
        if known != key:
            raise ValueError("Location is not in the administration tree.")
        return self.index[key]

    def load(self, line, row):
        cells = [row[c] for c in self.spec["key_columns"]]
        if any(c is None for c in cells):
            return self.issue(line, None, "skipped", "Key column is blank.")
        key = "|".join(text(c) for c in cells)
        parent = None
        if self.parents is not None:
            cells = [row[c] for c in self.spec["parent_key_columns"]]
            if any(c is None for c in cells):
                return self.issue(line, None, "skipped",
                                  "Parent key column is blank.")
            parent = self.parents.get("|".join(text(c) for c in cells))
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
        self.records[key] = data
        self.seen.add(key)
        self.loaded += 1


def _unblocked(proposal, blocked, chosen):
    """The Proposal cut down to the chosen forms that are not blocked."""
    skip = {b["form"] for b in blocked}
    return cut_forms(proposal, {
        f["key"] for f in proposal["forms"]
        if f["key"] not in skip and (chosen is None or f["key"] in chosen)
    })


def apply_proposal(proposal, path, file_name, tenant, user, forms=None,
                   resolutions=None):
    """Apply a Proposal to the tenant and return the Onboarding Report.

    The ambiguity checks run again first: only the chosen forms (all
    when None) that are not blocked now are applied; the blocked ones
    are reported. Levels, units and forms are all-or-nothing: on any
    error none exist and the error propagates. Rows then load one by
    one, each in its own savepoint; a bad row is skipped and reported,
    never fatal.
    """
    sheets = read_sheets(path, file_name)
    blocked = blocked_forms(proposal, sheets, tenant, user, resolutions)
    proposal = _unblocked(proposal, blocked, forms)
    index = admin_index(tenant)
    before = len(index)
    scope = user_scope(user)
    with transaction.atomic():
        refusal = check_hierarchy(proposal, tenant, user)
        if refusal:
            raise OnboardingError(refusal)
        places = Places(proposal, index, resolutions)
        _add_administration(
            proposal["administration"], places.unit_paths(proposal, sheets),
            tenant, index, scope,
        )
        forms = _create_forms(proposal["forms"], user)
    # The forms are committed: a failed refresh must not fail Apply.
    try:
        if len(index) > before:
            generate_sqlite(Administration, tenant=tenant)
        async_task("api.v1.v1_forms.tasks.refresh_form_config")
    except Exception:
        logger.exception("Data Onboarding: refresh after forms failed")

    # The causes' units hold names from the file: the Report keeps none.
    report = {"forms": [], "issues": [], "blocked": [
        {"form": b["form"], "name": b["name"], "causes": [
            {"kind": c["kind"], "reason": c["reason"]} for c in b["causes"]
        ]} for b in blocked
    ]}
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
            line = i + 2  # i is 0-based after a header row
            issues = len(rows.issues)
            try:
                with transaction.atomic():
                    rows.load(line, row)
            except Exception:
                logger.exception("Data Onboarding: row %s failed", line)
                del rows.issues[issues:]
                rows.issue(line, None, "skipped", ROW_FAILED)
        report["forms"].append({
            "key": spec["form"], "name": form.name, "form": form.id,
            "loaded": rows.loaded,
        })
        report["issues"] += rows.issues
    try:
        refresh_materialized_data()
    except Exception:
        logger.exception("Data Onboarding: refresh after rows failed")
    return report
