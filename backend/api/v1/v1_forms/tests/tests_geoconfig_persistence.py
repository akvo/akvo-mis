"""GEO-010: `extra.geoConfig` must survive every hop, and only sane values
may enter.

The failure this guards against is silent. `Questions.extra` is a free-form
JSONField that no code path claims ownership of, so a filter added anywhere
between the form builder and the device would strip `geoConfig` without
raising anything. The form would still look configured in the builder and
the device would quietly fall back to its defaults.

Two chains are asserted separately because they read from different places:

  builder  create -> publish -> snapshot -> GET (reads the snapshot)
  device   create -> publish -> activate -> live rows (reads live rows)

The second one is the one that matters most. `enabled_geoshape_question_ids`
queries live rows, so a `geoConfig` lost during `restore_from_snapshot`
turns overlap detection off for every published form with no error anywhere.
"""

import copy
import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.functions import (
    _geo_config_issues,
    normalize_form_definition,
    validate_form_definition,
)
from api.v1.v1_forms.models import Forms, Questions, UserForms
from api.v1.v1_mobile.geometry import enabled_geoshape_question_ids
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_mobile.tests.mixins import AssignmentTokenTestHelperMixin
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser


# The shape GEO-009's authoring panel writes: numbers as numbers, the
# switch as a real boolean, all three nested under extra.geoConfig.
GEO_CONFIG = {
    "accuracyThreshold": 15,
    "detectOverlaps": True,
    "overlapThreshold": 20,
}

FORM_PAYLOAD = {
    "name": "Plot Registration",
    "type": 1,
    "approval_instructions": None,
    "parent": None,
    "question_group": [
        {
            "id": None,
            "name": "plot_info",
            "label": "Plot Information",
            "order": 1,
            "repeatable": False,
            "repeat_text": None,
            "question": [
                {
                    "id": None,
                    "order": 1,
                    "label": "Farmer name",
                    "short_label": None,
                    "name": "farmer_name",
                    "type": "input",
                    "meta": True,
                    "required": True,
                    "rule": None,
                    "dependency": None,
                    "dependency_rule": "AND",
                    "api": None,
                    "extra": None,
                    "tooltip": None,
                    "fn": None,
                    "pre": None,
                    "display_only": False,
                    "option": [],
                },
                {
                    "id": None,
                    "order": 2,
                    "label": "Plot boundary",
                    "short_label": None,
                    "name": "plot_boundary",
                    "type": "geoshape",
                    "meta": False,
                    "required": True,
                    "rule": None,
                    "dependency": None,
                    "dependency_rule": "AND",
                    "api": None,
                    "extra": {"geoConfig": GEO_CONFIG},
                    "tooltip": None,
                    "fn": None,
                    "pre": None,
                    "display_only": False,
                    "option": [],
                },
            ],
        }
    ],
}

# Every one of these has been seen in the wild or is one keystroke away
# from it: the editor's generic custom-parameter tab array-wraps and
# stringifies (GEO-009 §4), hand-edited JSON gets the range wrong, and
# `True` passes an `isinstance(value, int)` check in Python.
INVALID_GEO_CONFIGS = [
    {"overlapThreshold": 0},
    {"overlapThreshold": 101},
    {"overlapThreshold": "20"},
    {"overlapThreshold": ["20"]},
    {"accuracyThreshold": -5},
    {"accuracyThreshold": 0},
    {"accuracyThreshold": True},
    {"detectOverlaps": "true"},
    {"detectOverlaps": ["true"]},
    {"detectOverlaps": 1},
    # `allowTapping` (GEO-014 D-4) is checked as strictly as
    # `detectOverlaps`: it defaults to true and only `false` does
    # anything, so a truthy `"false"` would read as enabled here and as
    # disabled to nobody.
    {"allowTapping": "false"},
    {"allowTapping": ["false"]},
    {"allowTapping": 0},
    # Authorable since editor 2.0.6 (GEO-010 §6). Each was specified
    # long before anything could write it; the panel closed that gap on
    # the authoring side and left this one open on the storage side.
    {"validateShape": "true"},
    {"validateArea": 1},
    {"validateOverlap": ["false"]},
    {"maxAreaHa": 0},
    {"maxAreaHa": -20},
    {"maxAreaHa": "20"},
    {"maxAreaHa": True},
    {"overlapThresholdFloor": 0},
    {"overlapThresholdFloor": 101},
    {"overlapThresholdFloor": "5"},
    # The pair rule: each value passes its own range check, and the
    # clamp still receives its bounds inverted (GEO-014 D-5).
    {"overlapThresholdFloor": 50, "overlapThreshold": 20},
    # Inverted against the DEFAULT ceiling, with none authored - the
    # effective clamp is just as broken as the explicit pair above.
    {"overlapThresholdFloor": 50},
    "not an object",
    [],
]


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


def _payload(geo_config=GEO_CONFIG):
    """Form payload whose geoshape question carries `geo_config`."""
    payload = copy.deepcopy(FORM_PAYLOAD)
    payload["question_group"][0]["question"][1]["extra"] = {
        "geoConfig": geo_config
    }
    return payload


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoConfigPersistenceTestCase(TestCase, AssignmentTokenTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        # The editor sends JS timestamp IDs, which leave the PK sequences
        # far behind the seeded rows; without this, inserts collide.
        with connection.cursor() as cur:
            for tbl in ["form", "question_group", "question", "option"]:
                cur.execute(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tbl}', 'id'),"
                    f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                    f"false)"
                )
        self.header = _login(self.client)
        self.admin = SystemUser.objects.filter(email="admin@akvo.org").first()
        self.passcode = "geo10test"

    # ── request helpers ──────────────────────────────────────────

    def _create(self, payload=None):
        return self.client.post(
            "/api/v1/manage/forms",
            json.dumps(payload or _payload()),
            content_type="application/json",
            **self.header,
        )

    def _create_ok(self, payload=None):
        res = self._create(payload)
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()["id"]

    def _publish(self, form_id):
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()

    def _get(self, form_id):
        return self.client.get(
            f"/api/v1/manage/forms/{form_id}", **self.header
        )

    def _put(self, form_id, payload):
        return self.client.put(
            f"/api/v1/manage/forms/{form_id}",
            json.dumps(payload),
            content_type="application/json",
            **self.header,
        )

    def _geoshape(self, form_id):
        return Questions.objects.get(form_id=form_id, name="plot_boundary")

    def _device_geoshape(self, form_id):
        """The geoshape question as the device receives it."""
        token = self.get_assignment_token(self.passcode)
        res = self.client.get(
            f"/api/v1/device/form/{form_id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200, res.content)
        questions = res.json()["question_group"][0]["question"]
        return next(q for q in questions if q["name"] == "plot_boundary")

    def _assign_to_device(self, form_id):
        form = Forms.objects.get(pk=form_id)
        UserForms.objects.get_or_create(user=self.admin, form=form)
        assignment = MobileAssignment.objects.create_assignment(
            user=self.admin, name="plot device", passcode=self.passcode
        )
        root = Administration.objects.filter(parent__isnull=True).first()
        assignment.administrations.add(*root.parent_administration.all())
        assignment.forms.add(form)
        return assignment

    def _put_new_threshold(self, form_id, threshold):
        """Re-save the published form with a changed overlap threshold.

        Reads the form back first: the editor PUTs whatever GET handed it,
        so this exercises the same round trip the builder does.
        """
        payload = self._get(form_id).json()
        question = payload["question_group"][0]["question"][1]
        question["extra"]["geoConfig"]["overlapThreshold"] = threshold
        res = self._put(form_id, payload)
        self.assertEqual(res.status_code, 200, res.content)
        return res

    # ── the config reaches storage ───────────────────────────────

    def test_publish_carries_geoconfig_into_the_snapshot(self):
        form_id = self._create_ok()
        self._publish(form_id)
        schema = Forms.objects.get(pk=form_id).active_version.schema
        question = schema["question_group"][0]["question"][1]
        self.assertEqual(question["extra"], {"geoConfig": GEO_CONFIG})

    def test_published_put_keeps_geoconfig_in_the_new_snapshot(self):
        form_id = self._create_ok()
        self._publish(form_id)
        self._put_new_threshold(form_id, 35)

        form = Forms.objects.get(pk=form_id)
        pending = form.published_versions.order_by("-version").first()
        self.assertNotEqual(pending, form.active_version)
        question = pending.schema["question_group"][0]["question"][1]
        self.assertEqual(
            question["extra"]["geoConfig"],
            {**GEO_CONFIG, "overlapThreshold": 35},
        )

    # ── the config reaches the device gate ───────────────────────

    def test_publish_leaves_the_question_in_the_overlap_gate(self):
        """`enabled_geoshape_question_ids` reads live rows, and it is the
        only thing standing between a configured form and overlap
        detection silently doing nothing."""
        form_id = self._create_ok()
        self._publish(form_id)
        form = Forms.objects.get(pk=form_id)
        self.assertEqual(
            enabled_geoshape_question_ids(form),
            [self._geoshape(form_id).id],
        )

    def test_detect_overlaps_false_keeps_the_question_out_of_the_gate(self):
        """The mirror of the test above. Without it, a gate that ignored
        the stored value and returned every geoshape question would still
        look correct."""
        form_id = self._create_ok(
            _payload({**GEO_CONFIG, "detectOverlaps": False})
        )
        self._publish(form_id)
        self.assertEqual(
            enabled_geoshape_question_ids(Forms.objects.get(pk=form_id)),
            [],
        )

    def test_activate_restores_geoconfig_into_live_rows(self):
        """Publishing a pending snapshot copies it back over the live rows.
        A `geoConfig` dropped here would disable overlap detection on a form
        whose builder still shows the setting."""
        form_id = self._create_ok()
        self._publish(form_id)
        self._put_new_threshold(form_id, 35)
        self._publish(form_id)

        question = self._geoshape(form_id)
        self.assertEqual(
            question.extra["geoConfig"],
            {**GEO_CONFIG, "overlapThreshold": 35},
        )
        self.assertEqual(
            enabled_geoshape_question_ids(Forms.objects.get(pk=form_id)),
            [question.id],
        )

    # ── the config reaches the device ────────────────────────────

    def test_mobile_form_detail_returns_geoconfig_unchanged(self):
        form_id = self._create_ok()
        self._publish(form_id)
        self._assign_to_device(form_id)
        self.assertEqual(
            self._device_geoshape(form_id)["extra"],
            {"geoConfig": GEO_CONFIG},
        )

    def test_device_sees_an_edit_only_after_it_is_published(self):
        """Not a bug, and asserted so it stays deliberate: a PUT on a
        published form writes a pending snapshot only (FB-002B D-6), while
        the device reads live rows. Until someone publishes, the builder
        shows the new threshold and the device is still on the old one."""
        form_id = self._create_ok()
        self._publish(form_id)
        self._assign_to_device(form_id)

        self._put_new_threshold(form_id, 35)
        self.assertEqual(
            self._device_geoshape(form_id)["extra"]["geoConfig"][
                "overlapThreshold"
            ],
            20,
        )

        self._publish(form_id)
        self.assertEqual(
            self._device_geoshape(form_id)["extra"]["geoConfig"][
                "overlapThreshold"
            ],
            35,
        )

    # ── nonsense is refused at the boundary ──────────────────────

    def test_create_rejects_nonsensical_geoconfig(self):
        for geo_config in INVALID_GEO_CONFIGS:
            with self.subTest(geo_config=geo_config):
                res = self._create(_payload(geo_config))
                self.assertEqual(res.status_code, 400, res.content)
                self.assertIn("geoConfig", res.json()["message"])
                self.assertFalse(
                    Questions.objects.filter(name="plot_boundary").exists(),
                    "a rejected payload must not write any question",
                )

    def test_put_rejects_nonsensical_geoconfig(self):
        form_id = self._create_ok()
        payload = self._get(form_id).json()
        question = payload["question_group"][0]["question"][1]
        question["extra"]["geoConfig"]["overlapThreshold"] = 500

        res = self._put(form_id, payload)
        self.assertEqual(res.status_code, 400, res.content)
        self.assertEqual(
            self._geoshape(form_id).extra["geoConfig"]["overlapThreshold"],
            20,
            "a rejected PUT must leave the stored config alone",
        )

    def test_valid_variants_are_stored_as_sent(self):
        """Three ways of saying "leave this one alone", all legal: an absent
        key, an explicit null (how the builder spells an unset value, the
        same as every other nullable question field), and a key this version
        has never heard of, so an older backend still accepts a form
        authored against a newer builder."""
        for config in (
            {"accuracyThreshold": 8},
            {"detectOverlaps": True, "overlapThreshold": None},
            {"allowTapping": False},
            {"validateShape": False, "validateArea": True},
            {"validateOverlap": False},
            {"maxAreaHa": 0.001},
            # Equal bounds are a degenerate clamp, not an inverted one:
            # the threshold is pinned rather than undefined.
            {"overlapThresholdFloor": 20, "overlapThreshold": 20},
            {"overlapThresholdFloor": 5, "overlapThreshold": 60},
            # A floor under the default ceiling needs no ceiling authored.
            {"overlapThresholdFloor": 3},
            # Independent since 2026-09-21: overlap detection on while
            # tapping stays allowed is a legal, deliberate combination.
            {"detectOverlaps": True, "allowTapping": True},
            {**GEO_CONFIG, "futureKnob": "whatever"},
        ):
            with self.subTest(config=config):
                form_id = self._create_ok(_payload(config))
                self.assertEqual(
                    self._geoshape(form_id).extra, {"geoConfig": config}
                )


class GeoConfigImportValidationTestCase(TestCase):
    """The builder API is not the only way a form gets written. JSON import
    (FB-007) reaches the same rows through its own validator, so the same
    rules have to be enforced there (GEO-010 D-1)."""

    def _definition(self, geo_config):
        return {
            "id": 990001,
            "name": "Imported Plot Form",
            "type": 1,
            "question_group": [
                {
                    "id": 990100,
                    "name": "plot_info",
                    "label": "Plot Information",
                    "order": 1,
                    "question": [
                        {
                            "id": 990200,
                            "name": "plot_boundary",
                            "label": "Plot boundary",
                            "type": "geoshape",
                            "order": 1,
                            "questionGroupId": 990100,
                            "required": True,
                            "meta": False,
                            "dependency": None,
                            "displayOnly": False,
                            "extra": {"geoConfig": geo_config},
                            "option": [],
                        }
                    ],
                }
            ],
        }

    def _issues(self, geo_config):
        norm = normalize_form_definition(self._definition(geo_config))
        return validate_form_definition(norm, check_entities=False)

    def test_valid_geoconfig_imports_cleanly(self):
        self.assertEqual(
            [i for i in self._issues(GEO_CONFIG) if i["level"] == "error"],
            [],
        )

    def test_invalid_geoconfig_blocks_the_import(self):
        for geo_config in INVALID_GEO_CONFIGS:
            with self.subTest(geo_config=geo_config):
                errors = [
                    i
                    for i in self._issues(geo_config)
                    if i["level"] == "error"
                    and i["code"] == "invalid_geo_config"
                ]
                self.assertTrue(errors, "import must refuse this config")
                self.assertIn("geoConfig", errors[0]["path"])


class GeoConfigPairValidationTestCase(TestCase):
    """The clamp pair, isolated.

    Every other check in `_geo_config_issues` reads one key. This one
    reads two, which is why it lives in its own function and gets its
    own case: a reviewer looking for "what is different about this rule"
    should find it stated once rather than inferred from a parametrised
    list.
    """

    def test_an_inverted_pair_is_reported_once_on_the_floor(self):
        issues = _geo_config_issues(
            {"overlapThresholdFloor": 50, "overlapThreshold": 20}
        )
        self.assertEqual(len(issues), 1)
        subpath, message = issues[0]
        self.assertEqual(subpath, "extra.geoConfig.overlapThresholdFloor")
        self.assertIn("overlapThreshold", message)

    def test_a_malformed_value_reports_its_type_error_alone(self):
        """No comparison against a string on top of the type error.
        Two messages about one mistake reads as two mistakes."""
        issues = _geo_config_issues(
            {"overlapThresholdFloor": "50", "overlapThreshold": 20}
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("must be a number", issues[0][1])

    def test_an_out_of_range_value_is_not_also_compared(self):
        issues = _geo_config_issues(
            {"overlapThresholdFloor": 101, "overlapThreshold": 20}
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("greater than 0", issues[0][1])

    def test_defaults_participate_in_the_comparison(self):
        """A floor of 50 with no ceiling clamps against the default 20,
        so it is inverted in effect even though only one key was
        authored. The editor bounds each input by the other and reaches
        the same answer; D-1 is why the API cannot rely on that."""
        self.assertEqual(
            len(_geo_config_issues({"overlapThresholdFloor": 50})), 1
        )
        self.assertEqual(
            _geo_config_issues({"overlapThresholdFloor": 3}), []
        )

    def test_a_ceiling_alone_is_never_inverted(self):
        """The default floor is 5, below every legal ceiling."""
        for ceiling in (5, 20, 100):
            with self.subTest(ceiling=ceiling):
                self.assertEqual(
                    _geo_config_issues({"overlapThreshold": ceiling}), []
                )
