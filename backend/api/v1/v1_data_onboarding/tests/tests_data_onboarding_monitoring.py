import copy
import io
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_data_onboarding.apply import apply_proposal
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant
from utils.tenant_test_case import TenantIsolationTestCase

URL = "/api/v1/data-onboarding"

SITES = [
    ["site_id", "site_name", "district"],
    ["S1", "Alpha", "North"],
    ["S2", "Beta", "South"],
]
VISITS = [
    ["site", "date", "status"],
    ["S1", "2026-01-05", "Working"],
    ["S1", "2026-02-05", "Broken"],
    ["S2", "2026-01-07", "Working"],
    ["S9", "2026-01-08", "Working"],   # orphan: no site S9
    ["S1", "2026-01-05", "Broken"],    # repeated visit key
    ["", "2026-01-09", "Working"],     # blank parent key
]


def q(name, type, required=False, meta=False, option=(), extra=None):
    return {
        "name": name, "label": name.title(), "type": type,
        "required": required, "meta": meta,
        "option": [{"label": o, "value": o.lower()} for o in option],
        "rule": None, "extra": extra, "tooltip": None, "dependency": [],
        "dependency_rule": "AND",
    }


def spec(form, sheet, key_columns, parent_key_columns=(), admin=(),
         columns=()):
    return {
        "form": form, "sheet": sheet, "key_columns": list(key_columns),
        "parent_key_columns": list(parent_key_columns),
        "administration_columns": list(admin), "geo": None,
        "columns": [{"question": c, "column": c} for c in columns],
        "value_maps": [], "date_format": None, "multi_separator": None,
        "unmapped_columns": [],
    }


PROPOSAL = {
    "administration": {
        "levels": ["Country", "District"],
        "source": {"sheet": "sites", "columns": ["district"]},
        "aliases": [],
    },
    "forms": [
        # Monitoring first: Apply must not depend on the order.
        {
            "key": "visits", "name": "Site visits", "type": "monitoring",
            "parent": "sites",
            "question_group": [{"name": "visit", "label": "Visit",
                                "repeatable": False,
                                "question": [
                                    q("date", "date", required=True),
                                    q("status", "option",
                                      option=("Working", "Broken")),
                                ]}],
        },
        {
            "key": "sites", "name": "Water sites", "type": "registration",
            "parent": None,
            "question_group": [{"name": "site", "label": "Site",
                                "repeatable": False,
                                "question": [
                                    q("location", "cascade", required=True,
                                      extra={"type": "administration"}),
                                    q("site_name", "input", required=True,
                                      meta=True),
                                ]}],
        },
    ],
    "data": [
        spec("visits", "visits", ["site", "date"], ["site"],
             columns=["date", "status"]),
        spec("sites", "sites", ["site_id"], admin=["district"],
             columns=["site_name"]),
    ],
    "notes": [],
}


def xlsx(sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@override_settings(USE_TZ=False, TEST_ENV=True)
class MonitoringApplyTestCase(TestCase):
    """apply_proposal with a registration sheet and a visit sheet."""

    def setUp(self):
        self.tenant = Tenant.objects.create(subdomain="fresh")
        level = Levels.objects.create(name="Country", level=0,
                                      tenant=self.tenant)
        Administration.objects.create(
            parent=None, level=level, name="Kenya", tenant=self.tenant
        )
        self.user = SystemUser.objects.create_superuser(
            email="admin@fresh.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=self.tenant,
        )
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def apply(self):
        path = os.path.join(self.dir, "sites.xlsx")
        with open(path, "wb") as fh:
            fh.write(xlsx({"sites": SITES, "visits": VISITS}))
        return apply_proposal(PROPOSAL, path, "sites.xlsx", self.tenant,
                              self.user)

    def test_visits_load_under_their_registration_records(self):
        report = self.apply()

        sites = Forms.objects.get(tenant=self.tenant, name="Water sites")
        visits = Forms.objects.get(tenant=self.tenant, name="Site visits")
        self.assertEqual(visits.parent, sites)

        alpha = FormData.objects.get(form=sites, name="Alpha")
        beta = FormData.objects.get(form=sites, name="Beta")
        loaded = FormData.objects.filter(form=visits).order_by("id")
        self.assertEqual(
            [(v.parent, v.uuid, v.administration, v.name) for v in loaded],
            [(alpha, alpha.uuid, alpha.administration, "Alpha"),
             (alpha, alpha.uuid, alpha.administration, "Alpha"),
             (beta, beta.uuid, beta.administration, "Beta")],
        )
        self.assertEqual(loaded[1].data_answer.get(question__name="status")
                         .options, ["broken"])

        by_key = {f["key"]: f["loaded"] for f in report["forms"]}
        self.assertEqual(by_key, {"sites": 2, "visits": 3})
        self.assertEqual(
            [(i["sheet"], i["row"], i["question"], i["kind"])
             for i in report["issues"]],
            [("visits", 5, None, "skipped"),
             ("visits", 6, None, "skipped"),
             ("visits", 7, None, "skipped")],
        )
        reasons = " ".join(i["reason"] for i in report["issues"])
        self.assertNotIn("S9", reasons)


def openai_client(content):
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return client


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", OPENAI_API_KEY="sk-test-mock-key",
    TEST_ENV=True,
)
class MonitoringEndpointTestCase(TenantIsolationTestCase):
    def setUp(self):
        super().setUp()
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store)

        def upload(file, folder=None, filename=None):
            shutil.copyfile(file, os.path.join(self.store, filename))

        def download(url):
            return os.path.join(self.store, url.split("/")[-1])

        for target, fake in (
            ("api.v1.v1_data_onboarding.views.storage.upload", upload),
            ("api.v1.v1_data_onboarding.tasks.storage.download", download),
        ):
            p = patch(target, side_effect=fake)
            p.start()
            self.addCleanup(p.stop)
        p = patch("api.v1.v1_data_onboarding.views.async_task",
                  return_value="task-id")
        p.start()
        self.addCleanup(p.stop)
        # The tenant fixture's root is "Kenya"; units go under it.
        self.headers = {
            **self.auth(self.a["user"]),
            "HTTP_HOST": f"{self.a['tenant'].subdomain}.app.com",
        }

    def draft(self, proposal):
        from api.v1.v1_data_onboarding.tasks import draft_proposal

        res = self.client.post(
            URL, {"file": SimpleUploadedFile(
                "sites.xlsx", xlsx({"sites": SITES, "visits": VISITS})
            )}, **self.headers,
        )
        pk = res.json()["id"]
        with patch("openai.OpenAI",
                   return_value=openai_client(json.dumps(proposal))):
            draft_proposal(pk)
        return pk, self.client.get(f"{URL}/{pk}", **self.headers).json()

    def test_a_monitoring_form_must_have_a_registration_parent_in_the_proposal(
        self,
    ):
        cases = {
            "unknown parent": "elsewhere",
            "no parent": None,
            "monitoring parent": "visits",
        }
        for name, parent in cases.items():
            with self.subTest(name):
                p = copy.deepcopy(PROPOSAL)
                p["forms"][0]["parent"] = parent
                _, body = self.draft(p)
                self.assertEqual(body["status"], "failed")
                self.assertIn("parent", body["error"])

    def test_a_monitoring_form_loses_its_location_question(self):
        p = copy.deepcopy(PROPOSAL)
        p["forms"][0]["question_group"][0]["question"].insert(
            0, q("location", "cascade", extra={"type": "administration"})
        )
        _, body = self.draft(p)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"]["forms"], PROPOSAL["forms"])

    def test_a_monitoring_form_copying_its_parent_rows_is_dropped(self):
        p = copy.deepcopy(PROPOSAL)
        p["data"][0].update(sheet="sites", key_columns=["site_id"],
                            parent_key_columns=["site_id"],
                            columns=[{"question": "status",
                                      "column": "site_name"}])
        _, body = self.draft(p)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(
            [f["key"] for f in body["proposal"]["forms"]], ["sites"]
        )
        self.assertEqual(
            [d["form"] for d in body["proposal"]["data"]], ["sites"]
        )

    def test_visit_rows_need_parent_key_columns(self):
        p = copy.deepcopy(PROPOSAL)
        p["data"][0]["parent_key_columns"] = []
        _, body = self.draft(p)
        self.assertEqual(body["status"], "failed")
        self.assertIn("parent_key_columns", body["error"])

    def test_upload_to_applied_with_linked_visits(self):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding

        pk, body = self.draft(PROPOSAL)
        self.assertEqual(body["status"], "proposed")
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(f"{URL}/{pk}/apply", **self.headers)
        self.assertEqual(res.status_code, 200)
        with patch("openai.OpenAI") as openai:
            apply_onboarding(pk, self.a["user"].id)
        openai.assert_not_called()

        report = self.client.get(f"{URL}/{pk}", **self.headers).json()[
            "report"]
        by_key = {f["key"]: f for f in report["forms"]}
        self.assertEqual(by_key["visits"]["loaded"], 3)
        self.assertEqual(
            [(i["sheet"], i["row"], i["kind"]) for i in report["issues"]],
            [("visits", 5, "skipped"), ("visits", 6, "skipped"),
             ("visits", 7, "skipped")],
        )

        alpha = FormData.objects.get(form_id=by_key["sites"]["form"],
                                     name="Alpha")
        res = self.client.get(
            f"/api/v1/form-data/{by_key['visits']['form']}"
            f"?page=1&parent={alpha.uuid}",
            **self.headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total"], 2)
