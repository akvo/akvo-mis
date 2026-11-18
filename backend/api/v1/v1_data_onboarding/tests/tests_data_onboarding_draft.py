import io
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

from utils.tenant_test_case import TenantIsolationTestCase

URL = "/api/v1/data-onboarding"

CSV = (
    "site_id;site_name;district;water_source\n"
    "S-001;Alpha well;North;BH\n"
    "S-002;Beta well;South;Well\n"
    "S-003;Gamma well;North;BH\n"
)


def proposal(**overrides):
    p = {
        "administration": {
            "levels": ["Country", "District"],
            "source": {"sheet": "csv", "columns": ["district"]},
            "units": [["North"], ["South"]],
            "aliases": [],
        },
        "forms": [
            {
                "key": "sites",
                "name": "Water sites",
                "type": "registration",
                "parent": None,
                "question_group": [
                    {
                        "name": "site",
                        "label": "Site",
                        "question": [
                            {
                                "name": "location",
                                "label": "Location",
                                "type": "cascade",
                                "required": True,
                                "meta": False,
                                "option": [],
                                "rule": None,
                                "extra": {"type": "administration"},
                            },
                            {
                                "name": "site_name",
                                "label": "Site name",
                                "type": "input",
                                "required": True,
                                "meta": True,
                                "option": [],
                                "rule": None,
                                "extra": None,
                            },
                            {
                                "name": "water_source",
                                "label": "Water source",
                                "type": "option",
                                "required": False,
                                "meta": False,
                                "option": [
                                    {"label": "Borehole", "value": "borehole"},
                                    {"label": "Well", "value": "well"},
                                ],
                                "rule": None,
                                "extra": None,
                            },
                        ],
                    }
                ],
            }
        ],
        "data": [
            {
                "form": "sites",
                "sheet": "csv",
                "key_columns": ["site_id"],
                "administration_columns": ["district"],
                "geo": None,
                "columns": [
                    {"question": "site_name", "column": "site_name"},
                    {"question": "water_source", "column": "water_source"},
                ],
                "value_maps": [
                    {
                        "question": "water_source",
                        "values": [{"raw": "BH", "label": "Borehole"}],
                    }
                ],
                "date_format": None,
                "multi_separator": None,
                "unmapped_columns": [],
            }
        ],
        "notes": ["site_id identifies each site."],
    }
    p.update(overrides)
    return p


def openai_client(content):
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return client


def xlsx(rows):
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", OPENAI_API_KEY="sk-test-mock-key"
)
class DataOnboardingDraftTestCase(TenantIsolationTestCase):
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
            ("api.v1.v1_data_onboarding.tasks.download", download),
        ):
            p = patch(target, side_effect=fake)
            p.start()
            self.addCleanup(p.stop)
        p = patch(
            "api.v1.v1_data_onboarding.views.async_task",
            return_value="task-id",
        )
        self.async_task = p.start()
        self.addCleanup(p.stop)

    def host(self, t="a"):
        return {"HTTP_HOST": f"{getattr(self, t)['tenant'].subdomain}.app.com"}

    def upload(self, name, content, t="a"):
        return self.client.post(
            URL,
            {"file": SimpleUploadedFile(name, content)},
            **self.auth(getattr(self, t)["user"]),
            **self.host(t),
        )

    def get(self, pk, t="a"):
        return self.client.get(
            f"{URL}/{pk}", **self.auth(getattr(self, t)["user"]),
            **self.host(t),
        )

    def draft(self, pk, content):
        from api.v1.v1_data_onboarding.tasks import draft_proposal

        client = openai_client(content)
        with patch("openai.OpenAI", return_value=client):
            draft_proposal(pk)
        return client

    def test_refuses_a_file_that_is_not_csv_or_xlsx(self):
        res = self.upload("data.json", b"{}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("CSV or xlsx", res.json()["message"])
        self.async_task.assert_not_called()

    def test_refuses_a_file_over_10_mb(self):
        res = self.upload("data.csv", b"a\n" + b"x" * (10 * 1024 * 1024))
        self.assertEqual(res.status_code, 400)
        self.assertIn("10 MB", res.json()["message"])

    def test_refuses_more_than_50000_rows(self):
        res = self.upload("data.csv", b"a\n" + b"1\n" * 50001)
        self.assertEqual(res.status_code, 400)
        self.assertIn("50,000 rows", res.json()["message"])

    def test_refuses_an_unreadable_xlsx(self):
        res = self.upload("data.xlsx", b"not a workbook")
        self.assertEqual(res.status_code, 400)
        self.assertIn("could not be read", res.json()["message"])

    def test_upload_drafts_a_proposal_from_a_semicolon_csv(self):
        res = self.upload("sites.csv", CSV.encode())
        self.assertEqual(res.status_code, 201)
        pk = res.json()["id"]
        self.assertEqual(res.json()["status"], "drafting")
        self.async_task.assert_called_once()
        self.assertEqual(self.get(pk).json()["status"], "drafting")

        client = self.draft(pk, json.dumps(proposal()))

        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["file_name"], "sites.csv")
        self.assertEqual(body["proposal"], proposal())
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["response_format"]["type"], "json_schema")
        self.assertTrue(kwargs["response_format"]["json_schema"]["strict"])
        sent = json.dumps(kwargs["messages"])
        # The delimiter was detected: columns reach the profile split.
        for column in ("site_id", "site_name", "district", "water_source"):
            self.assertIn(f'\\"{column}\\"', sent)

    @override_settings(DATA_ONBOARDING_OPENAI_MODEL="gpt-test-model")
    def test_uses_the_configured_model(self):
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        client = self.draft(pk, json.dumps(proposal()))
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-test-model")

    def test_only_category_like_columns_send_their_values(self):
        rows = [["code", "category"]]
        rows += [[f"MARKER{i:04d}", ["red", "blue"][i % 2]] for i in range(40)]
        pk = self.upload("markers.xlsx", xlsx(rows)).json()["id"]
        client = self.draft(pk, "not json")

        sent = json.dumps(client.chat.completions.create.call_args.kwargs)
        self.assertNotIn("MARKER", sent)
        self.assertIn("red", sent)
        self.assertIn("blue", sent)

    def test_invalid_output_fails_the_draft(self):
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps({"forms": []}))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "failed")
        self.assertIsNone(body["proposal"])
        self.assertTrue(body["error"])

    def test_a_proposal_naming_a_column_not_in_the_file_fails(self):
        p = proposal()
        p["data"][0]["key_columns"] = ["no_such_column"]
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(p))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("no_such_column", body["error"])

    def test_a_form_the_definition_import_rejects_fails(self):
        p = proposal()
        p["forms"][0]["name"] = ""
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(p))
        self.assertEqual(self.get(pk).json()["status"], "failed")

    def test_value_maps_only_for_category_like_columns(self):
        p = proposal()
        p["administration"]["source"]["sheet"] = "Sheet"
        p["data"][0]["sheet"] = "Sheet"
        p["data"][0]["value_maps"] = [
            {"question": "site_name", "values": [{"raw": "x", "label": "y"}]}
        ]
        rows = [["site_id", "site_name", "district", "water_source"]]
        rows += [[f"S{i}", f"Site {i}", "North", "BH"] for i in range(40)]
        pk = self.upload("sites.xlsx", xlsx(rows)).json()["id"]
        self.draft(pk, json.dumps(p))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("site_name", body["error"])

    def test_an_openai_error_fails_the_draft(self):
        from api.v1.v1_data_onboarding.tasks import draft_proposal

        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("boom")
        with patch("openai.OpenAI", return_value=client):
            draft_proposal(pk)
        self.assertEqual(self.get(pk).json()["status"], "failed")

    def test_another_tenant_cannot_see_the_record(self):
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.assertEqual(self.get(pk, t="b").status_code, 404)

    def test_upload_requires_the_permission(self):
        from api.v1.v1_users.models import SystemUser

        user = SystemUser.objects.create_user(
            email="plain@acme.org", password="Secret#Pass123",
            first_name="P", last_name="P", tenant=self.a["tenant"],
        )
        res = self.client.post(
            URL, {"file": SimpleUploadedFile("a.csv", CSV.encode())},
            **self.auth(user), **self.host(),
        )
        self.assertEqual(res.status_code, 403)
