import copy
import csv
import os
import shutil
import tempfile

from django.db import transaction
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_data_onboarding.apply import apply_proposal
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant

HEADER = [
    "id", "name", "district", "village", "count", "source", "visited",
    "tags", "lat", "lng", "gps",
]
GOOD = {
    "id": "S1", "name": "Alpha", "district": "KwaZulu-Natal",
    "village": "Hill", "count": "12", "source": "BH",
    "visited": "2026-03-04", "tags": "Red; Blue", "lat": "-1.5",
    "lng": "36.8", "gps": "",
}


def q(name, type, required=False, meta=False, option=(), extra=None):
    return {
        "name": name, "label": name.title(), "type": type,
        "required": required, "meta": meta,
        "option": [{"label": o, "value": v} for o, v in option],
        "rule": None, "extra": extra,
    }


PROPOSAL = {
    "administration": {
        "levels": ["Country", "District", "Village"],
        "source": {"sheet": "csv", "columns": ["district", "village"]},
        "units": [],
        "aliases": [],
    },
    "forms": [{
        "key": "sites", "name": "Water sites", "type": "registration",
        "parent": None,
        "question_group": [{"name": "site", "label": "Site", "question": [
            q("location", "cascade", required=True,
              extra={"type": "administration"}),
            q("name", "input", required=True, meta=True),
            q("count", "number"),
            q("source", "option",
              option=[("Borehole", "borehole"), ("Hand pump", "hand_pump")]),
            q("visited", "date"),
            q("tags", "multiple_option",
              option=[("Red", "red"), ("Blue", "blue")]),
            q("gps", "geo"),
        ]}],
    }],
    "data": [{
        "form": "sites", "sheet": "csv", "key_columns": ["id"],
        "parent_key_columns": [],
        "administration_columns": ["district", "village"],
        "geo": {"lat": "lat", "lng": "lng", "column": None},
        "columns": [
            {"question": "name", "column": "name"},
            {"question": "count", "column": "count"},
            {"question": "source", "column": "source"},
            {"question": "visited", "column": "visited"},
            {"question": "tags", "column": "tags"},
        ],
        "value_maps": [{"question": "source",
                        "values": [{"raw": "BH", "label": "Borehole"}]}],
        "date_format": None,
        "multi_separator": None,
        "unmapped_columns": [],
    }],
    "notes": [],
}


@override_settings(USE_TZ=False, TEST_ENV=True)
class ApplyProposalTestCase(TestCase):
    """The check-and-apply service: Proposal + file + tenant + user."""

    def setUp(self):
        self.tenant = Tenant.objects.create(subdomain="fresh")
        level = Levels.objects.create(name="Country", level=0,
                                      tenant=self.tenant)
        self.root = Administration.objects.create(
            parent=None, level=level, name="Kenya", tenant=self.tenant
        )
        self.user = SystemUser.objects.create_superuser(
            email="admin@fresh.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=self.tenant,
        )
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def apply(self, rows, proposal=PROPOSAL, header=HEADER, **kw):
        path = os.path.join(self.dir, "sites.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows([[r.get(c, "") for c in header] for r in rows])
        return apply_proposal(proposal, path, "sites.csv", self.tenant,
                              self.user, **kw)

    def answers(self, record):
        out = {}
        for a in record.data_answer.all():
            out[a.question.name] = (
                a.options if a.options is not None
                else a.value if a.value is not None else a.name
            )
        return out

    def test_a_fresh_tenant_gets_levels_units_a_form_and_records(self):
        report = self.apply([GOOD, {**GOOD, "id": "S2", "name": "Beta",
                                    "village": "Vale"}])

        self.assertEqual(
            list(Levels.objects.filter(tenant=self.tenant)
                 .order_by("level").values_list("name", flat=True)),
            ["Country", "District", "Village"],
        )
        district = Administration.objects.get(
            tenant=self.tenant, parent=self.root
        )
        self.assertEqual(district.name, "KwaZulu-Natal")  # not title-cased
        self.assertEqual(
            sorted(district.parent_administration.values_list(
                "name", flat=True)),
            ["Hill", "Vale"],
        )

        form = Forms.objects.get(tenant=self.tenant, name="Water sites")
        self.assertEqual(form.status, FormStatus.published)
        self.assertIsNotNone(form.active_version)
        self.assertTrue(
            UserForms.objects.filter(user=self.user, form=form).exists()
        )

        records = FormData.objects.filter(form=form).order_by("id")
        self.assertEqual(records.count(), 2)
        alpha = records[0]
        self.assertFalse(alpha.is_pending)
        self.assertEqual(alpha.name, "Alpha")
        self.assertEqual(alpha.administration.name, "Hill")
        self.assertEqual(alpha.geo, [-1.5, 36.8])
        self.assertEqual(alpha.published_version, form.active_version)
        self.assertEqual(self.answers(alpha), {
            "location": alpha.administration.id, "name": "Alpha",
            "count": 12, "source": ["borehole"], "visited": "2026-03-04",
            "tags": ["blue", "red"], "gps": [-1.5, 36.8],
        })
        self.assertEqual(report["forms"], [
            {"key": "sites", "name": "Water sites", "form": form.id,
             "loaded": 2},
        ])
        self.assertEqual(report["issues"], [])

    def test_a_failing_form_leaves_no_levels_units_or_forms(self):
        p = copy.deepcopy(PROPOSAL)
        broken = copy.deepcopy(p["forms"][0])
        broken.update(key="broken", name="")
        p["forms"].append(broken)
        with self.assertRaises(ValueError):
            self.apply([GOOD], proposal=p)
        self.assertEqual(Levels.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(
            Administration.objects.filter(tenant=self.tenant).count(), 1
        )
        self.assertFalse(Forms.objects.filter(tenant=self.tenant).exists())

    def test_aliases_and_unit_names_ignore_case_and_spaces(self):
        p = copy.deepcopy(PROPOSAL)
        p["administration"]["aliases"] = [
            {"from": "kzn", "to": "KwaZulu-Natal"}
        ]
        report = self.apply([
            GOOD,
            {**GOOD, "id": "S2", "district": " KZN "},
            {**GOOD, "id": "S3", "district": "kwazulu-natal",
             "village": "HILL"},
        ], proposal=p)
        self.assertEqual(report["forms"][0]["loaded"], 3)
        self.assertEqual(
            list(Administration.objects.filter(tenant=self.tenant)
                 .values_list("name", flat=True).order_by("id")),
            ["Kenya", "KwaZulu-Natal", "Hill"],
        )
        self.assertEqual(
            {d.administration.name for d in FormData.objects.all()}, {"Hill"}
        )

    def test_row_rules(self):
        def spec(**kw):
            p = copy.deepcopy(PROPOSAL)
            p["data"][0].update(kw)
            return p

        def required(name):
            p = copy.deepcopy(PROPOSAL)
            for question in p["forms"][0]["question_group"][0]["question"]:
                if question["name"] == name:
                    question["required"] = True
            return p

        # name, rows, proposal, loaded answers or None, issues
        # (row, question, kind) where row 2 is the first data row
        cases = [
            ("required blank skips the row",
             [{**GOOD, "name": ""}], PROPOSAL, None,
             [(2, "name", "skipped")]),
            ("required invalid skips the row",
             [{**GOOD, "count": "lots"}], required("count"), None,
             [(2, "count", "skipped")]),
            ("optional invalid is dropped with a warning",
             [{**GOOD, "count": "lots", "source": "Tap"}], PROPOSAL,
             {"count": None, "source": None},
             [(2, "count", "warning"), (2, "source", "warning")]),
            ("blank key skips the row",
             [{**GOOD, "id": ""}], PROPOSAL, None, [(2, None, "skipped")]),
            ("a repeated key loads only the first row",
             [GOOD, {**GOOD, "name": "Again"}], PROPOSAL, {"name": "Alpha"},
             [(3, None, "skipped")]),
            ("value maps ignore case and surrounding spaces",
             [{**GOOD, "source": "  bh "}], PROPOSAL,
             {"source": ["borehole"]}, []),
            ("option values come from labels",
             [{**GOOD, "source": "HAND PUMP"}], PROPOSAL,
             {"source": ["hand_pump"]}, []),
            ("a value mapped to blank is no answer",
             [{**GOOD, "source": "x"}],
             spec(value_maps=[{"question": "source", "values": [
                 {"raw": "X", "label": ""}]}]),
             {"source": None}, []),
            ("only empty cells are blank",
             [{**GOOD, "name": "NA"}], PROPOSAL, {"name": "NA"}, []),
            ("a blank location skips the row",
             [{**GOOD, "village": ""}], PROPOSAL, None,
             [(2, "location", "skipped")]),
            ("numbers drop units and thousands separators",
             [{**GOOD, "count": "$1,200 kg"}], PROPOSAL, {"count": 1200},
             []),
            ("dates use the stated format",
             [{**GOOD, "visited": "03/04/2026"}], spec(date_format="%d/%m/%Y"),
             {"visited": "2026-04-03"}, []),
            ("ambiguous dates need a format",
             [{**GOOD, "visited": "03/04/2026"}], PROPOSAL,
             {"visited": None}, [(2, "visited", "warning")]),
            ("multi-select splits on common separators",
             [{**GOOD, "tags": "blue|RED / blue"}], PROPOSAL,
             {"tags": ["blue", "red"]}, []),
            ("multi-select splits on the stated separator",
             [{**GOOD, "tags": "Red+Blue"}], spec(multi_separator=r"\+"),
             {"tags": ["blue", "red"]}, []),
            ("one bad choice drops the whole multi-select answer",
             [{**GOOD, "tags": "Red; Green"}], PROPOSAL, {"tags": None},
             [(2, "tags", "warning")]),
            ("geo from one combined column",
             [{**GOOD, "gps": "-2.25, 37.5"}],
             spec(geo={"lat": None, "lng": None, "column": "gps"}),
             {"gps": [-2.25, 37.5]}, []),
            ("geo out of range is dropped",
             [{**GOOD, "lat": "95"}], PROPOSAL, {"gps": None},
             [(2, "gps", "warning")]),
            ("a blank latitude is no geo answer",
             [{**GOOD, "lat": ""}], PROPOSAL, {"gps": None}, []),
        ]
        for name, rows, proposal, answers, issues in cases:
            # Each case rolls back, so every case starts on a fresh tenant.
            with self.subTest(name), transaction.atomic():
                try:
                    report = self.apply(rows, proposal=proposal)
                    self.assertEqual(
                        [(i["row"], i["question"], i["kind"])
                         for i in report["issues"]],
                        issues,
                    )
                    for issue in report["issues"]:
                        self.assertEqual(issue["sheet"], "csv")
                        for row in rows:
                            for column in ("name", "count", "source", "tags",
                                           "visited", "district", "lat"):
                                if len(row[column]) > 2:
                                    self.assertNotIn(row[column],
                                                     issue["reason"])
                    records = FormData.objects.filter(
                        form__tenant=self.tenant
                    )
                    if answers is None:
                        self.assertEqual(records.count(), 0)
                        continue
                    self.assertEqual(records.count(), 1)
                    got = self.answers(records.get())
                    for question, value in answers.items():
                        self.assertEqual(got.get(question), value)
                finally:
                    transaction.set_rollback(True)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AmbiguousAdministrationTestCase(TestCase):
    """Each case blocks its form; the other forms still apply."""

    setUp = ApplyProposalTestCase.setUp
    apply = ApplyProposalTestCase.apply

    def tree(self, levels, units):
        """Levels below the root, and units as paths of names."""
        made = [Levels.objects.get(tenant=self.tenant, level=0)]
        for depth, name in enumerate(levels, 1):
            made.append(Levels.objects.create(
                tenant=self.tenant, name=name, level=depth
            ))
        nodes = {(): self.root}
        for path in units:
            for depth in range(1, len(path) + 1):
                key = tuple(path[:depth])
                if key not in nodes:
                    nodes[key] = Administration.objects.create(
                        parent=nodes[key[:-1]], level=made[depth],
                        name=path[depth - 1], tenant=self.tenant,
                    )

    def proposal(self, columns=("district", "village"), aliases=()):
        p = copy.deepcopy(PROPOSAL)
        p["administration"]["source"]["columns"] = list(columns)
        p["administration"]["aliases"] = [
            {"from": a, "to": b} for a, b in aliases
        ]
        p["data"][0]["administration_columns"] = list(columns)
        return p

    def kinds(self, report):
        return {
            b["form"]: sorted({c["kind"] for c in b["causes"]})
            for b in report["blocked"]
        }

    def test_ambiguity_cases(self):
        two_levels = (["District", "Village"],
                      [["KwaZulu-Natal", "Hill"], ["Coast", "Kwale"]])
        # name, (levels, units) or None, rows, proposal, blocked kinds
        cases = [
            ("a clean file blocks nothing", two_levels,
             [GOOD, {**GOOD, "id": "S2", "village": "Vale"}],
             self.proposal(), {}),
            ("more location columns than levels",
             (["District"], [["KwaZulu-Natal"]]),
             [GOOD], self.proposal(), {"sites": ["level_mapping"]}),
            ("a column missing in the middle",
             (["Province", "District", "Village"],
              [["East", "KwaZulu-Natal", "Hill"]]),
             [GOOD], self.proposal(), {"sites": ["level_mapping"]}),
            ("a name under several parents without a parent column",
             (["District", "Village"],
              [["KwaZulu-Natal", "Hill"], ["Coast", "Hill"]]),
             [{**GOOD, "district": "Hill"}], self.proposal(["district"]),
             {"sites": ["level_mapping", "shared_name"]}),
            ("a near-match spelling", two_levels,
             [GOOD, {**GOOD, "id": "S2", "district": "Coast",
                     "village": "Kwalle"}],
             self.proposal(), {"sites": ["near_match"]}),
            ("a near-match after normalizing punctuation", two_levels,
             [{**GOOD, "district": "Kwa Zulu Natal"}],
             self.proposal(), {"sites": ["near_match"]}),
            ("an alias is input to the checks", two_levels,
             [{**GOOD, "district": "Coast", "village": "Kwalle"}],
             self.proposal(aliases=[("kwalle", "Kwale")]), {}),
            ("a registration sheet with no location column",
             None, [GOOD], self.proposal([]), {"sites": ["no_location"]}),
        ]
        for name, tree, rows, proposal, blocked in cases:
            with self.subTest(name), transaction.atomic():
                try:
                    if tree:
                        self.tree(*tree)
                        # No new levels on a populated tree.
                        proposal["administration"]["levels"] = \
                            ["Country"] + tree[0]
                    units = Administration.objects.filter(
                        tenant=self.tenant).count()
                    report = self.apply(rows, proposal=proposal)
                    self.assertEqual(self.kinds(report), blocked)
                    created = Forms.objects.filter(tenant=self.tenant)
                    if not blocked:
                        self.assertEqual(created.count(), 1)
                        self.assertEqual(report["forms"][0]["loaded"],
                                         len(rows))
                        continue
                    self.assertFalse(created.exists())
                    self.assertEqual(report["forms"], [])
                    if tree:  # a blocked form adds no units
                        self.assertEqual(Administration.objects.filter(
                            tenant=self.tenant).count(), units)
                    for cause in report["blocked"][0]["causes"]:
                        self.assertTrue(cause["reason"])
                finally:
                    transaction.set_rollback(True)

    def test_unblocked_forms_apply_and_a_blocked_parent_blocks_monitoring(
        self
    ):
        p = self.proposal()
        nowhere = copy.deepcopy(p["forms"][0])
        nowhere.update(key="nowhere", name="No location")
        visits = copy.deepcopy(p["forms"][0])
        visits.update(key="visits", name="Visits", type="monitoring",
                      parent="nowhere")
        visits["question_group"][0]["question"] = [
            q("note", "input", meta=True)
        ]
        p["forms"] += [nowhere, visits]
        p["data"].append({**copy.deepcopy(p["data"][0]), "form": "nowhere",
                          "administration_columns": []})

        report = self.apply([GOOD], proposal=p)

        self.assertEqual(self.kinds(report), {
            "nowhere": ["no_location"], "visits": ["parent_blocked"],
        })
        self.assertEqual(
            list(Forms.objects.filter(tenant=self.tenant)
                 .values_list("name", flat=True)),
            ["Water sites"],
        )
        self.assertEqual(report["forms"][0]["loaded"], 1)

    def test_only_the_chosen_forms_apply(self):
        p = self.proposal()
        other = copy.deepcopy(p["forms"][0])
        other.update(key="other", name="Other sites")
        p["forms"].append(other)
        p["data"].append({**copy.deepcopy(p["data"][0]), "form": "other"})

        report = self.apply([GOOD], proposal=p, forms=["other"])

        self.assertEqual([f["key"] for f in report["forms"]], ["other"])
        self.assertEqual(
            list(Forms.objects.filter(tenant=self.tenant)
                 .values_list("name", flat=True)),
            ["Other sites"],
        )

    def test_rows_outside_the_subtree_are_not_ambiguous(self):
        from api.v1.v1_profile.constants import (
            FeatureAccessTypes,
            FeatureTypes,
        )
        from api.v1.v1_profile.models import (
            Role,
            RoleFeatureAccess,
            UserRole,
        )

        self.tree(["District", "Village"],
                  [["KwaZulu-Natal", "Hill"], ["Coast", "Kwale"]])
        mine = Administration.objects.get(name="KwaZulu-Natal")
        self.user = SystemUser.objects.create_user(
            email="team@fresh.org", password="Secret#Pass123",
            first_name="T", last_name="T", tenant=self.tenant,
        )
        role = Role.objects.create(name="team",
                                   administration_level=mine.level)
        RoleFeatureAccess.objects.create(
            role=role, type=FeatureTypes.data_onboarding,
            access=FeatureAccessTypes.data_onboard,
        )
        UserRole.objects.create(user=self.user, role=role,
                                administration=mine)

        report = self.apply(
            [GOOD, {**GOOD, "id": "S2", "district": "Coast",
                    "village": "Kwalle"}],
            proposal=self.proposal(),
        )

        self.assertEqual(report["blocked"], [])
        self.assertEqual(report["forms"][0]["loaded"], 1)
