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

    def apply(self, rows, proposal=PROPOSAL, header=HEADER):
        path = os.path.join(self.dir, "sites.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows([[r.get(c, "") for c in header] for r in rows])
        return apply_proposal(proposal, path, "sites.csv", self.tenant,
                              self.user)

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
