import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_data_onboarding.tests import tests_data_onboarding_draft as d
from api.v1.v1_data_onboarding.tests.tests_data_onboarding_draft import (
    CSV,
    URL,
    proposal,
)
from api.v1.v1_profile.models import Administration, Levels
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(
    USE_TZ=False, BASE_DOMAIN="app.com", OPENAI_API_KEY="sk-test-mock-key",
    TEST_ENV=True,
)
class ResolveAmbiguityTestCase(TenantIsolationTestCase):
    """Structured edits resolve each Ambiguous Administration cause."""

    _draft = d.DataOnboardingDraftTestCase  # not a global: runs once
    host, upload, get = _draft.host, _draft.upload, _draft.get
    draft, add_unit, apply = _draft.draft, _draft.add_unit, _draft.apply

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

    def onboard(self, content=CSV, p=None):
        pk = self.upload("sites.csv", content.encode()).json()["id"]
        self.draft(pk, json.dumps(p or proposal()))
        return pk

    def edit(self, pk, **body):
        with patch("openai.OpenAI") as openai:
            res = self.client.post(
                f"{URL}/{pk}/edits", body, content_type="application/json",
                **self.auth(self.a["user"]), **self.host(),
            )
        openai.assert_not_called()
        return res

    def kinds(self, pk):
        return {
            b["form"]: [c["kind"] for c in b["causes"]]
            for b in self.get(pk).json()["blocked"]
        }

    def apply_now(self, pk):
        from api.v1.v1_data_onboarding.tasks import apply_onboarding

        self.assertEqual(self.apply(pk).status_code, 200)
        apply_onboarding(pk, forms=self.async_task.call_args.kwargs["forms"])
        body = self.get(pk).json()
        self.assertEqual(body["status"], "applied")
        return body["report"]

    def located(self, form_id):
        return sorted(
            (d.name, d.administration.name)
            for d in FormData.objects.filter(form_id=form_id)
        )

    def units(self, name):
        return Administration.objects.filter(
            tenant=self.a["tenant"], name=name
        ).count()

    def test_a_near_match_resolved_to_the_existing_unit_applies(self):
        self.add_unit("Norths")
        pk = self.onboard()
        self.assertEqual(self.kinds(pk), {"sites": ["near_match"]})

        res = self.edit(pk, op="resolve_near_match", name="North",
                        match="Norths", use="existing")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["blocked"], [])
        self.assertEqual(res.json()["proposal"], proposal())  # names kept out
        report = self.apply_now(pk)
        self.assertEqual(self.located(report["forms"][0]["form"]), [
            ("Alpha well", "Norths"), ("Beta well", "South"),
            ("Gamma well", "Norths"),
        ])
        self.assertEqual(self.units("North"), 0)

    @override_settings(DATA_ONBOARDING_DAILY_CAP=2)
    def test_resolutions_survive_a_revision_and_stay_out_of_openai(self):
        from api.v1.v1_data_onboarding.tasks import revise_proposal

        self.add_unit("Norths")
        pk = self.onboard()  # the draft: 1 of 2
        for use in ("new", "existing"):  # edits use none of the cap
            self.edit(pk, op="resolve_near_match", name="North",
                      match="Norths", use=use)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                f"{URL}/{pk}/revise", {"instruction": "Rename the form"},
                content_type="application/json",
                **self.auth(self.a["user"]), **self.host(),
            )
        self.assertEqual(res.status_code, 200)

        client = d.openai_client(json.dumps(proposal()))
        with patch("openai.OpenAI", return_value=client):
            revise_proposal(*self.async_task.call_args.args[1:])

        body = self.get(pk).json()
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["blocked"], [])
        sent = json.dumps(client.chat.completions.create.call_args.kwargs)
        self.assertNotIn("Norths", sent)

    def test_a_near_match_confirmed_as_new_adds_the_unit(self):
        self.add_unit("Norths")
        pk = self.onboard()

        res = self.edit(pk, op="resolve_near_match", name="North",
                        match="Norths", use="new")

        self.assertEqual(res.json()["blocked"], [])
        report = self.apply_now(pk)
        self.assertEqual(self.located(report["forms"][0]["form"]), [
            ("Alpha well", "North"), ("Beta well", "South"),
            ("Gamma well", "North"),
        ])
        self.assertEqual(self.units("Norths"), 1)

    def tree(self, *paths):
        """District > Village units; tenant a has the district level."""
        village = Levels.objects.create(
            name="village", level=2, tenant=self.a["tenant"]
        )
        nodes = {}
        for district, name in paths:
            if district not in nodes:
                nodes[district] = Administration.objects.create(
                    parent=self.a["root"], level=self.a["child_level"],
                    name=district, tenant=self.a["tenant"],
                )
            Administration.objects.create(
                parent=nodes[district], level=village, name=name,
                tenant=self.a["tenant"],
            )
        return nodes

    def located_proposal(self, columns):
        p = proposal()
        p["administration"].update(
            levels=["Country", "District", "Village"], units=[],
            source={"sheet": "csv", "columns": columns},
        )
        p["data"][0]["administration_columns"] = columns
        return p

    VILLAGES = (
        "site_id;site_name;district;village;water_source\n"
        "S-001;Alpha well;North;Hill;BH\n"
        "S-002;Beta well;South;Dale;BH\n"
        "S-003;Gamma well;North;Vale;BH\n"
    )

    def test_a_level_mapping_is_resolved_by_picking_the_columns(self):
        self.tree(("North", "Hill"), ("South", "Dale"), ("North", "Vale"))
        pk = self.onboard(self.VILLAGES, self.located_proposal(
            ["village", "district", "water_source"]
        ))
        self.assertEqual(
            set(self.kinds(pk)["sites"]), {"level_mapping"}
        )

        res = self.edit(pk, op="map_level", form="sites",
                        columns=["district", "village"], level=1)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["blocked"], [])
        report = self.apply_now(pk)
        self.assertEqual(self.located(report["forms"][0]["form"]), [
            ("Alpha well", "Hill"), ("Beta well", "Dale"),
            ("Gamma well", "Vale"),
        ])

    def test_a_name_under_several_parents_is_resolved_by_its_parent(self):
        nodes = self.tree(("North", "Hill"), ("South", "Hill"),
                          ("North", "Vale"))
        content = (
            "site_id;site_name;village;water_source\n"
            "S-001;Alpha well;Hill;BH\n"
            "S-002;Beta well;Vale;BH\n"
        )
        pk = self.onboard(content, self.located_proposal(["village"]))
        self.assertEqual(self.kinds(pk),
                         {"sites": ["level_mapping", "shared_name"]})

        self.edit(pk, op="map_level", form="sites", columns=["village"],
                  level=2)
        body = self.get(pk).json()
        self.assertEqual(body["blocked"][0]["causes"], [{
            "kind": "shared_name",
            "reason": body["blocked"][0]["causes"][0]["reason"],
            "units": [{"name": "Hill", "parents": [
                {"id": nodes["North"].id, "name": "North"},
                {"id": nodes["South"].id, "name": "South"},
            ]}],
        }])

        res = self.edit(pk, op="choose_parent", name="Hill",
                        parent=nodes["South"].id)

        self.assertEqual(res.json()["blocked"], [])
        self.assertNotIn("Hill", json.dumps(res.json()["proposal"]))
        report = self.apply_now(pk)
        records = FormData.objects.filter(form_id=report["forms"][0]["form"])
        self.assertEqual(
            sorted((d.name, d.administration.parent.name) for d in records),
            [("Alpha well", "South"), ("Beta well", "North")],
        )

    def no_location(self):
        p = proposal()
        p["administration"].update(
            units=[], source={"sheet": None, "columns": []}
        )
        p["data"][0]["administration_columns"] = []
        return p

    def test_a_form_with_no_location_is_pointed_at_a_column(self):
        pk = self.onboard(p=self.no_location())
        self.assertEqual(self.kinds(pk), {"sites": ["no_location"]})

        res = self.edit(pk, op="set_location_column", form="sites",
                        column="district")

        self.assertEqual(res.json()["blocked"], [])
        report = self.apply_now(pk)
        self.assertEqual(self.located(report["forms"][0]["form"]), [
            ("Alpha well", "North"), ("Beta well", "South"),
            ("Gamma well", "North"),
        ])

    def test_a_form_with_no_location_can_be_dropped(self):
        p = self.no_location()
        other = {**proposal()["forms"][0], "key": "other",
                 "name": "Other sites"}
        p["forms"].append(other)
        p["data"].append({**proposal()["data"][0], "form": "other"})
        p["administration"]["source"] = {"sheet": "csv",
                                         "columns": ["district"]}
        pk = self.onboard(p=p)
        self.assertEqual(self.kinds(pk), {"sites": ["no_location"]})

        res = self.edit(pk, op="drop_form", form="sites")

        self.assertEqual(
            [f["key"] for f in res.json()["proposal"]["forms"]], ["other"]
        )
        self.assertEqual(res.json()["blocked"], [])
        report = self.apply_now(pk)
        self.assertEqual([f["name"] for f in report["forms"]],
                         ["Other sites"])

    def test_refused_edits_change_nothing(self):
        self.add_unit("Norths")
        pk = self.onboard()
        before = self.get(pk).json()
        for body in (
            {"op": "rewrite_everything"},
            {"op": "resolve_near_match", "name": "South", "match": "Norths",
             "use": "existing"},
            {"op": "resolve_near_match", "name": "North", "match": "Norths",
             "use": "maybe"},
            {"op": "map_level", "form": "sites", "columns": ["nope"],
             "level": 1},
            {"op": "choose_parent", "name": "North", "parent": 1},
            {"op": "drop_form", "form": "nope"},
        ):
            with self.subTest(body):
                res = self.edit(pk, **body)
                self.assertEqual(res.status_code, 400)
                self.assertTrue(res.json()["message"])
                self.assertEqual(self.get(pk).json(), before)

    def test_only_a_proposed_record_of_the_tenant_can_be_edited(self):
        pk = self.onboard()
        body = {"op": "drop_form", "form": "sites"}
        res = self.client.post(
            f"{URL}/{pk}/edits", body, content_type="application/json",
            **self.auth(self.b["user"]), **self.host("b"),
        )
        self.assertEqual(res.status_code, 404)
        self.apply(pk)
        self.assertEqual(self.edit(pk, **body).status_code, 400)
