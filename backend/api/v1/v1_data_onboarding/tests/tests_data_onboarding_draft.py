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
    "S-002;Beta well;South;BH\n"
    "S-003;Gamma well;North;BH\n"
)


def proposal(**overrides):
    p = {
        "administration": {
            "levels": ["Country", "District"],
            "source": {"sheet": "csv", "columns": ["district"]},
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
                "parent_key_columns": [],
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
            ("api.v1.v1_data_onboarding.tasks.storage.download", download),
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

    def test_location_columns_mapped_to_the_location_question_are_moved(self):
        # A shape gpt-4o-mini drafts: the location column feeds the
        # administration question and administration_columns is empty.
        drafted = proposal()
        spec = drafted["data"][0]
        spec["administration_columns"] = []
        spec["columns"].append({"question": "location", "column": "district"})
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]

        self.draft(pk, json.dumps(drafted))

        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["blocked"], [])
        self.assertEqual(body["proposal"], proposal())

    def test_a_column_fed_to_a_missing_question_is_listed_not_loaded(self):
        drafted = proposal()
        spec = drafted["data"][0]
        spec["columns"][1]["question"] = "source_kind"
        spec["unmapped_columns"] = [
            {"column": "site_id", "reason": "Not needed."}  # a key column
        ]
        drafted["data"].append({**spec, "form": "visits"})
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]

        self.draft(pk, json.dumps(drafted))

        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        expected = proposal()
        expected["data"][0].update(
            columns=expected["data"][0]["columns"][:1],
            value_maps=[],
            unmapped_columns=[{
                "column": "water_source",
                "reason": "The form has no question for this column.",
            }],
        )
        self.assertEqual(body["proposal"], expected)

    def test_an_option_question_on_a_column_never_listed_takes_text(self):
        drafted = proposal()
        drafted["forms"][0]["question_group"][0]["question"][1].update(
            type="option", option=[{"label": "Site name", "value": "name"}],
        )
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]

        self.draft(pk, json.dumps(drafted))

        self.assertEqual(self.get(pk).json()["proposal"], proposal())

    def test_aliases_that_rename_a_known_unit_or_invent_one_are_dropped(self):
        drafted = proposal()
        drafted["administration"]["aliases"] = [
            {"from": "acme-d", "to": "Acme District"},  # renames a unit
            {"from": "North", "to": "Northern"},  # a name from nowhere
            {"from": "Acme-dd", "to": "acme-d"},  # a misspelling: kept
        ]
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]

        self.draft(pk, json.dumps(drafted))

        self.assertEqual(
            self.get(pk).json()["proposal"]["administration"]["aliases"],
            [{"from": "Acme-dd", "to": "acme-d"}],
        )

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

    def test_a_small_file_sends_only_values_that_repeat(self):
        rows = [["name", "status"]]
        rows += [
            [f"MARKER{i:04d}", ["open", "closed", "pending"][i % 3]]
            for i in range(20)
        ]
        pk = self.upload("people.xlsx", xlsx(rows)).json()["id"]
        client = self.draft(pk, "not json")

        sent = json.dumps(client.chat.completions.create.call_args.kwargs)
        self.assertNotIn("MARKER", sent)
        for status in ("open", "closed", "pending"):
            self.assertIn(status, sent)

    def test_value_maps_for_columns_whose_values_do_not_repeat_go(self):
        p = proposal()
        p["administration"]["source"]["sheet"] = "Sheet"
        p["data"][0]["sheet"] = "Sheet"
        p["data"][0]["value_maps"] = [
            {"question": "site_name", "values": [{"raw": "x", "label": "y"}]}
        ]
        rows = [["site_id", "site_name", "district", "water_source"]]
        rows += [[f"S{i}", f"Site {i}", "North", "BH"] for i in range(20)]
        pk = self.upload("sites.xlsx", xlsx(rows)).json()["id"]
        self.draft(pk, json.dumps(p))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"]["data"][0]["value_maps"], [])

    def test_invalid_output_fails_the_draft(self):
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps({"forms": []}))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "failed")
        self.assertIsNone(body["proposal"])
        self.assertTrue(body["error"])

    def test_a_proposal_that_breaks_the_rules_is_sent_back_once(self):
        broken = proposal()
        broken["data"][0]["key_columns"] = ["no_such_column"]
        client = openai_client(None)
        client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=c))])
            for c in (json.dumps(broken), json.dumps(proposal()))
        ]
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        from api.v1.v1_data_onboarding.tasks import draft_proposal
        with patch("openai.OpenAI", return_value=client):
            draft_proposal(pk)

        self.assertEqual(self.get(pk).json()["status"], "proposed")
        fix = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertIn("no_such_column", fix[1]["content"])

    def test_a_form_no_data_spec_loads_fails(self):
        p = proposal(data=[])
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(p))
        body = self.get(pk).json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("no data spec loads 'sites'", body["error"])

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

    def test_value_maps_for_columns_with_many_values_go(self):
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
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"]["data"][0]["value_maps"], [])

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

    @override_settings(TEST_ENV=True)
    def test_upload_to_applied_report_and_email(self):
        from django.core import mail

        from api.v1.v1_data_onboarding.tasks import apply_onboarding

        content = CSV + "S-004;;South;BH\nS-001;Again;North;BH\n"
        pk = self.upload("sites.csv", content.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                f"{URL}/{pk}/apply", **self.auth(self.a["user"]),
                **self.host(),
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "applying")
        self.assertEqual(
            self.async_task.call_args.args,
            ("api.v1.v1_data_onboarding.tasks.apply_onboarding", pk,
             self.a["user"].id),
        )
        again = self.client.post(
            f"{URL}/{pk}/apply", **self.auth(self.a["user"]), **self.host()
        )
        self.assertEqual(again.status_code, 400)

        with patch("openai.OpenAI") as openai:
            apply_onboarding(pk, self.a["user"].id)
        openai.assert_not_called()

        body = self.get(pk).json()
        self.assertEqual(body["status"], "applied")
        form_id = body["report"]["forms"][0]["form"]
        self.assertEqual(body["report"]["forms"], [{
            "key": "sites", "name": "Water sites", "form": form_id,
            "loaded": 3,
        }])
        self.assertEqual(
            [(i["sheet"], i["row"], i["question"], i["kind"])
             for i in body["report"]["issues"]],
            [("csv", 5, "site_name", "skipped"), ("csv", 6, None, "skipped")],
        )

        data = self.client.get(
            f"/api/v1/form-data/{form_id}?page=1",
            **self.auth(self.a["user"]), **self.host(),
        ).json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(
            sorted(d["name"] for d in data["data"]),
            ["Alpha well", "Beta well", "Gamma well"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["admin@acme.org"])
        html = email.alternatives[0][0]
        self.assertIn(
            f"acme.app.com/control-center/data-onboarding/{pk}", html
        )
        self.assertIn("Water sites : 3", html)

    def add_unit(self, name):
        from api.v1.v1_profile.models import Administration

        Administration.objects.create(
            parent=self.a["root"], level=self.a["child_level"], name=name,
            tenant=self.a["tenant"],
        )

    def apply(self, pk, **body):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"{URL}/{pk}/apply", body, content_type="application/json",
                **self.auth(self.a["user"]), **self.host(),
            )

    def test_a_blocked_form_shows_its_cause_and_cannot_be_applied(self):
        self.add_unit("Norths")
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))

        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["proposal"], proposal())  # findings kept out
        self.assertEqual(body["blocked"], [{
            "form": "sites", "name": "Water sites", "causes": [{
                "kind": "near_match",
                "reason": body["blocked"][0]["causes"][0]["reason"],
                "units": [{"name": "North", "match": "Norths"}],
            }],
        }])
        for body in ({}, {"forms": ["sites"]}):
            res = self.apply(pk, **body)
            self.assertEqual(res.status_code, 400)
        self.assertEqual(self.get(pk).json()["status"], "proposed")

    def test_apply_takes_a_set_of_unblocked_forms(self):
        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))
        self.assertEqual(self.get(pk).json()["blocked"], [])

        for forms in (["nope"], [], "sites"):
            self.assertEqual(self.apply(pk, forms=forms).status_code, 400)
        res = self.apply(pk, forms=["sites"])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.async_task.call_args.kwargs["forms"], ["sites"])

    def test_apply_refuses_once_the_upload_is_purged(self):
        from api.v1.v1_data_onboarding.models import DataOnboarding

        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))
        DataOnboarding.objects.filter(id=pk).update(file=None)

        res = self.apply(pk)
        self.assertEqual(res.status_code, 400)
        self.assertIn("has been deleted", res.json()["message"])
        self.assertEqual(self.get(pk).json()["status"], "proposed")

    @override_settings(TEST_ENV=True)
    def test_a_failed_refresh_after_the_data_still_applies(self):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding

        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))
        self.assertEqual(self.apply(pk).status_code, 200)
        self.assertEqual(self.async_task.call_args.kwargs["timeout"], 3600)

        with patch(
            "api.v1.v1_data_onboarding.apply.refresh_materialized_data",
            side_effect=RuntimeError("view refresh"),
        ), patch("api.v1.v1_data_onboarding.apply.async_task",
                 side_effect=RuntimeError("queue down")):
            apply_onboarding(*self.async_task.call_args.args[1:])

        body = self.get(pk).json()
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["report"]["forms"][0]["key"], "sites")

    @override_settings(TEST_ENV=True)
    def test_apply_rechecks_against_the_tree_as_it_is_now(self):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding
        from api.v1.v1_forms.models import Forms

        pk = self.upload("sites.csv", CSV.encode()).json()["id"]
        self.draft(pk, json.dumps(proposal()))
        self.assertEqual(self.get(pk).json()["blocked"], [])
        self.assertEqual(self.apply(pk).status_code, 200)

        self.add_unit("Norths")  # the tree changed after review
        apply_onboarding(*self.async_task.call_args.args[1:],
                         forms=self.async_task.call_args.kwargs["forms"])

        body = self.get(pk).json()
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["report"]["forms"], [])
        self.assertEqual(
            [(b["form"], [c["kind"] for c in b["causes"]])
             for b in body["report"]["blocked"]],
            [("sites", ["near_match"])],
        )
        self.assertFalse(
            Forms.objects.filter(name="Water sites").exists()
        )
