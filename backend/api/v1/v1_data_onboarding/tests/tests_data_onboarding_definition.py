"""Form definitions (XLSForm and other layouts), and data-file hints."""
import csv
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import openpyxl
import pandas as pd
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data_onboarding.apply import apply_proposal
from api.v1.v1_data_onboarding.constants import DataOnboardingStatus
from api.v1.v1_data_onboarding.definition import MAX_DEFINITION_ROWS
from api.v1.v1_data_onboarding.hints import add_hints
from api.v1.v1_data_onboarding.models import DataOnboarding
from api.v1.v1_data_onboarding.profile import profile_sheets, read_sheets
from api.v1.v1_data_onboarding.proposal import validate_proposal
from api.v1.v1_data_onboarding.tasks import draft_proposal
from api.v1.v1_data_onboarding.tests.tests_data_onboarding_draft import (
    openai_client,
)
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant

XLSFORM = {
    "survey": [
        ["type", "name", "label", "hint", "required", "relevance",
         "calculation"],
        ["begin_group", "site", "Site"],
        ["select_one yn", "has_pump", "Has a pump?", None, "true"],
        ["integer", "pumps", "Number of pumps", "Count the working ones",
         "true", "${has_pump} = 'yes'"],
        ["geopoint", "gps", "GPS"],
        ["end_group"],
        ["begin_repeat", "visits", "Visits"],
        ["text", "comment", "Comment"],
        ["end_repeat"],
        ["calculate", "total", None, None, None, None, "1+1"],
    ],
    "choices": [["list_name", "name", "label"], ["yn", "yes", "Yes"],
                ["yn", "no", "No"]],
    "settings": [["id_string", "version"], ["pump_survey", "3"]],
}

# An Akvo Flow export: a title row, then two header rows.
FLOW = [
    ["New form (v. 11.0)"],
    ["Group", None, None, "Question"],
    ["#", "Title", "Repeatable", "# in group", "Text", "Question help",
     "Variable name", "Question type", "Mandatory", "Options"],
    ["1", "BASIC INFORMATION", None, "1", "What date is it?", None, None,
     "Date", "Yes", None],
]

DRAFTED = {
    "administration": {"levels": [], "source": {"sheet": None,
                                                "columns": []},
                       "aliases": []},
    "forms": [{
        "key": "survey", "name": "New form", "type": "registration",
        "parent": None,
        "question_group": [{
            "name": "basic", "label": "Basic information",
            "repeatable": False,
            "question": [{
                "name": "date", "label": "What date is it?", "type": "date",
                "required": True, "meta": False, "option": [], "rule": None,
                "extra": None, "tooltip": None, "dependency": [],
                "dependency_rule": "AND",
            }],
        }],
    }],
    "data": [],
    "notes": [],
}


def workbook(sheets, path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    wb.save(path)


@override_settings(USE_TZ=False, TEST_ENV=True,
                   OPENAI_API_KEY="sk-test-mock-key")
class FormDefinitionTestCase(TestCase):
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
        p = patch("api.v1.v1_data_onboarding.tasks.storage.download",
                  side_effect=lambda url: os.path.join(self.dir, url))
        p.start()
        self.addCleanup(p.stop)

    def draft(self, name, content=None):
        onboarding = DataOnboarding.objects.create(
            tenant=self.tenant, created_by=self.user, file=name,
            file_name=name, status=DataOnboardingStatus.drafting,
        )
        client = openai_client(json.dumps(content or DRAFTED))
        with patch("openai.OpenAI", return_value=client):
            draft_proposal(onboarding.id)
        onboarding.refresh_from_db()
        return onboarding, client

    def test_an_xlsform_becomes_its_form_without_openai(self):
        workbook(XLSFORM, os.path.join(self.dir, "pumps.xlsx"))

        onboarding, client = self.draft("pumps.xlsx")

        self.assertEqual(onboarding.error, None)
        self.assertEqual(onboarding.status, DataOnboardingStatus.proposed)
        client.chat.completions.create.assert_not_called()
        self.assertEqual(onboarding.profile["definition"], "xlsform")
        p = onboarding.proposal
        self.assertEqual(p["data"], [])
        [form] = p["forms"]
        self.assertEqual(form["name"], "Pump survey")
        site, visits = form["question_group"]
        self.assertEqual([q["name"] for q in site["question"]],
                         ["has_pump", "pumps", "gps"])
        self.assertTrue(visits["repeatable"])
        pumps = site["question"][1]
        self.assertEqual(pumps["tooltip"], "Count the working ones")
        self.assertEqual(pumps["dependency"][0]["question"], "has_pump")
        self.assertEqual(pumps["dependency"][0]["equal"], "yes")
        self.assertEqual(site["question"][0]["option"][0],
                         {"label": "Yes", "value": "yes"})
        self.assertTrue(any("total" in n for n in p["notes"]))

    def test_applying_an_xlsform_creates_the_form_with_its_logic(self):
        path = os.path.join(self.dir, "pumps.xlsx")
        workbook(XLSFORM, path)
        onboarding, _ = self.draft("pumps.xlsx")

        report = apply_proposal(onboarding.proposal, path, "pumps.xlsx",
                                self.tenant, self.user)

        [entry] = report["forms"]
        self.assertEqual(entry["loaded"], 0)
        form = Forms.objects.get(id=entry["form"])
        has_pump = Questions.objects.get(form=form, name="has_pump")
        pumps = Questions.objects.get(form=form, name="pumps")
        self.assertEqual(pumps.dependency,
                         [{"id": has_pump.id, "equal": "yes"}])
        self.assertEqual(pumps.tooltip, "Count the working ones")
        self.assertTrue(QuestionGroup.objects.get(
            form=form, name="visits").repeatable)

    def test_another_definition_layout_sends_only_its_sheets(self):
        workbook({"Full Survey": FLOW,
                  "Records": [["site", "phone"], ["Alpha", "0712 999 111"]]},
                 os.path.join(self.dir, "flow.xlsx"))

        onboarding, client = self.draft("flow.xlsx")

        self.assertEqual(onboarding.status, DataOnboardingStatus.proposed)
        self.assertEqual(onboarding.profile["definition_sheets"],
                         ["Full Survey"])
        kwargs = client.chat.completions.create.call_args.kwargs
        sent = json.dumps(kwargs["messages"])
        self.assertIn("form definition", kwargs["messages"][0]["content"])
        self.assertIn("What date is it?", sent)
        self.assertNotIn("0712 999 111", sent)
        self.assertEqual(onboarding.proposal["forms"][0]["name"], "New form")
        self.assertIn("Records", onboarding.proposal["notes"][-1])

    def test_code_settles_condition_values_and_sourceless_cascades(self):
        drafted = json.loads(json.dumps(DRAFTED))
        questions = drafted["forms"][0]["question_group"][0]["question"]
        base = questions[0]
        questions[:] = [
            {**base, "name": "org", "type": "cascade"},
            # Label and value swapped, as gpt-4o-mini drafted them.
            {**base, "name": "seen", "type": "option", "option": [
                {"label": "yes", "value": "Yes"},
                {"label": "no", "value": "No"},
            ]},
            {**base, "name": "what", "type": "input", "dependency": [
                {"question": "seen", "options": ["Yes", "maybe"],
                 "min": None, "max": None, "equal": None,
                 "notEqual": None},
            ]},
            {**base, "name": "when", "type": "input", "dependency": [
                {"question": "seen", "options": ["maybe"], "min": None,
                 "max": None, "equal": None, "notEqual": None},
            ]},
        ]
        workbook({"Full Survey": FLOW}, os.path.join(self.dir, "flow.xlsx"))

        onboarding, _ = self.draft("flow.xlsx", drafted)

        self.assertEqual(onboarding.error, None)
        got = {q["name"]: q for q in onboarding.proposal["forms"][0][
            "question_group"][0]["question"]}
        self.assertEqual(got["org"]["type"], "input")
        self.assertEqual(got["seen"]["option"][0],
                         {"label": "Yes", "value": "yes"})
        self.assertEqual(got["what"]["dependency"][0]["options"], ["yes"])
        self.assertEqual(got["when"]["dependency"], [])

    def test_a_long_sheet_is_data_whatever_its_headers(self):
        path = os.path.join(self.dir, "answers.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["question", "answer type", "respondent"])
            for i in range(MAX_DEFINITION_ROWS + 1):
                writer.writerow(["q", "x", f"marker-{i}"])

        _, client = self.draft("answers.csv")

        sent = json.dumps(client.chat.completions.create.call_args.kwargs[
            "messages"])
        self.assertNotIn("marker-", sent)
        self.assertNotIn("form definition", sent)

    def test_long_format_answers_are_data(self):
        path = os.path.join(self.dir, "answers.csv")
        with open(path, "w", newline="") as fh:
            csv.writer(fh).writerows([
                ["respondent", "question", "answer"],
                ["R1", "Age", "marker-34"], ["R1", "Sex", "F"],
            ])

        _, client = self.draft("answers.csv")

        sent = json.dumps(client.chat.completions.create.call_args.kwargs[
            "messages"])
        self.assertNotIn("marker-", sent)
        self.assertNotIn("form definition", sent)

    def test_a_paper_survey_is_a_definition(self):
        paper = [["Question", "Response"],
                 ["1. What date is it?", "__________"],
                 ["2. Do you have a pump?", "Yes____"]]
        workbook({"Paper": paper}, os.path.join(self.dir, "paper.xlsx"))

        onboarding, _ = self.draft("paper.xlsx")

        self.assertEqual(onboarding.profile["definition_sheets"], ["Paper"])

    def test_records_beside_their_codebook_are_data(self):
        codebook = [["Variable", "Question label", "Type"],
                    ["site", "Site name", "text"],
                    ["ph", "pH reading", "number"]]
        records = [["site", "ph"], ["Alpha", "7.1"], ["Beta", "marker-6"]]
        workbook({"Codebook": codebook, "Records": records},
                 os.path.join(self.dir, "data.xlsx"))

        onboarding, client = self.draft("data.xlsx")

        self.assertNotIn("definition", onboarding.profile)
        sent = json.dumps(client.chat.completions.create.call_args.kwargs[
            "messages"])
        self.assertNotIn("form definition", sent)

    def test_a_dependency_must_be_on_an_earlier_question(self):
        proposal = json.loads(json.dumps(DRAFTED))
        base = proposal["forms"][0]["question_group"][0]["question"][0]
        on = {"options": ["x"], "min": None, "max": None, "equal": None,
              "notEqual": None}
        proposal["forms"][0]["question_group"][0]["question"] = [
            {**base, "name": "a", "dependency": [{**on, "question": "b"}]},
            {**base, "name": "b", "dependency": [{**on, "question": "a"}]},
        ]

        errors = validate_proposal(proposal, {"definition": "layout",
                                              "sheets": []})

        self.assertEqual(errors, [
            "forms[0].a: depends on 'b', not an earlier question"])


class HintsTestCase(TestCase):
    CSV = (
        "site_id,site_name,district,village,lat,lon,phone,visit_date,ph\n"
        "S1,Alpha,North,Nyamira,-1.1,36.1,+254700000001,01/02/2024,7.1\n"
        "S1,Alpha,North,Nyamira,-1.1,36.1,+254700000001,03/02/2024,7.3\n"
        "S2,Beta,North,Kisii,-1.2,36.2,+254700000002,01/02/2024,6.9\n"
        "S2,Beta,North,Kisii,-1.2,36.2,+254700000002,04/02/2024,7.0\n"
        "S3,Gamma,South,Kendu,-1.3,36.3,+254700000003,01/02/2024,7.2\n"
        "S3,Gamma,South,Kendu,-1.3,36.3,+254700000003,05/02/2024,7.4\n"
    )

    def profile(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv") as fh:
            fh.write(self.CSV)
            fh.flush()
            sheets = read_sheets(fh.name, "visits.csv")
        return add_hints(sheets, profile_sheets(sheets))

    def test_hints_name_the_structure_of_a_visits_sheet(self):
        sheet = self.profile()["sheets"][0]
        [key] = sheet["registration_keys"]
        self.assertEqual(key["column"], "site_id")
        self.assertEqual(key["records"], 3)
        self.assertIn("village", key["constant_per_record"])
        self.assertEqual(key["varying"], ["visit_date", "ph"])
        self.assertEqual(sheet["hierarchy"], ["district", "village"])
        self.assertEqual(sheet["geo"], [{"lat": "lat", "lng": "lon"}])
        flags = {c["name"]: c.get("flags") for c in sheet["columns"]}
        self.assertEqual(flags["phone"], ["personal"])
        self.assertEqual(flags["visit_date"], ["day_month_order"])

    def test_a_personal_column_sends_no_values(self):
        sent = json.dumps(self.profile())
        self.assertNotIn("+2547", sent)

    def test_a_category_about_the_respondent_keeps_its_values(self):
        df = pd.DataFrame({"respondent_gender": ["Male", "Female"] * 5,
                           "phone": [f"+2547000000{i:02}" for i in range(10)]})
        sheets = {"s": df.astype(object)}
        columns = {c["name"]: c for c in add_hints(
            sheets, profile_sheets(sheets))["sheets"][0]["columns"]}
        self.assertNotIn("flags", columns["respondent_gender"])
        self.assertIn("values", columns["respondent_gender"])
        self.assertEqual(columns["phone"]["flags"], ["personal"])

    def test_a_column_holding_another_sheets_keys_is_linked(self):
        sites = {"site_id": ["S1", "S2"], "name": ["A", "B"]}
        visits = {"site": ["S1", "S1", "S2"], "ph": ["7", "8", "6"]}
        sheets = {"sites": pd.DataFrame(sites).astype(object),
                  "visits": pd.DataFrame(visits).astype(object)}
        profile = add_hints(sheets, profile_sheets(sheets))
        self.assertEqual(profile["links"],
                         [{"keys": "sites.site_id", "column": "visits.site"}])
