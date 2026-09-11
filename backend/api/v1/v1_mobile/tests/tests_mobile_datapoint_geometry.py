from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_mobile.geometry import geometry_answers
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


# Asymmetric on purpose: a lat/lng swap moves this from Ethiopia into the
# Indian Ocean, so the bbox assertions fail loudly instead of passing on
# coincidentally similar numbers.
ADDIS_PLOT = [[9.03, 38.74], [9.04, 38.74], [9.04, 38.75], [9.03, 38.75]]

LIST_ROW_KEYS = [
    "administration_id", "form_id", "id", "last_updated", "name", "url",
]


@override_settings(USE_TZ=False, TEST_ENV=True)
class MobileDatapointGeometryTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.child = self.administration.parent_administration.first()
        self.user = self.create_user(
            email="enumerator@test.org",
            role_level=self.IS_ADMIN,
            administration=self.administration,
        )

        self.form = self.make_form("Plot Form", detect_overlaps=True)
        self.plain_form = self.make_form("Plain Form", detect_overlaps=False)

        self.assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="device", passcode="passcode1234"
        )
        self.assignment.administrations.add(self.child)
        self.assignment.forms.add(self.form, self.plain_form)

        self.datapoint = self.make_datapoint(self.form, "Plot A", ADDIS_PLOT)

        auth = self.client.post(
            "/api/v1/device/auth",
            {"code": "passcode1234"},
            content_type="application/json",
        )
        self.token = auth.data["syncToken"]

    def make_form(self, name, detect_overlaps):
        form = Forms.objects.create(name=name, version=1)
        group = QuestionGroup.objects.create(
            form=form, name="Group", order=1
        )
        extra = (
            {"geoConfig": {"detectOverlaps": True}}
            if detect_overlaps else None
        )
        form.plot_question = Questions.objects.create(
            form=form, question_group=group, name="plot",
            label="Plot boundary", order=1,
            type=QuestionTypes.geoshape, extra=extra,
        )
        self.user.user_form.create(form=form)
        return form

    def make_datapoint(self, form, name, coordinates, index=0):
        datapoint = FormData.objects.create(
            name=name, form=form, administration=self.child,
            created_by=self.user, uuid=f"uuid-{name.lower().replace(' ', '')}",
        )
        if coordinates is not None:
            Answers.objects.create(
                data=datapoint, question=form.plot_question,
                options=coordinates, created_by=self.user, index=index,
            )
        return datapoint

    def get_list(self, query=""):
        return self.client.get(
            f"/api/v1/device/datapoint-list/{query}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )

    def test_geometry_is_served_when_the_flag_is_on(self):
        response = self.get_list(f"?form_id={self.form.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()["data"][0]
        self.assertEqual(len(row["geometry"]), 1)
        geometry = row["geometry"][0]
        self.assertEqual(geometry["question_id"], self.form.plot_question.id)
        self.assertEqual(geometry["index"], 0)
        self.assertEqual(geometry["coordinates"], ADDIS_PLOT)

    def test_bbox_matches_the_polygon(self):
        response = self.get_list(f"?form_id={self.form.id}")
        bbox = response.json()["data"][0]["geometry"][0]["bbox"]
        self.assertEqual(bbox, {
            "min_lat": 9.03, "max_lat": 9.04,
            "min_lon": 38.74, "max_lon": 38.75,
        })

    def test_bbox_of_a_polygon_crossing_the_equator(self):
        """Signed latitudes. Naive min/max is right here and abs() is
        not, so this catches the wrong instinct."""
        straddling = [[-0.5, 38.74], [0.5, 38.74], [0.5, 38.75]]
        self.make_datapoint(self.form, "Plot Eq", straddling)
        response = self.get_list(f"?form_id={self.form.id}")
        rows = {r["name"]: r for r in response.json()["data"]}
        self.assertEqual(rows["Plot Eq"]["geometry"][0]["bbox"], {
            "min_lat": -0.5, "max_lat": 0.5,
            "min_lon": 38.74, "max_lon": 38.75,
        })

    def test_no_geometry_key_when_the_flag_is_off(self):
        """The flag-off response keeps exactly today's shape."""
        self.make_datapoint(self.plain_form, "Plain A", ADDIS_PLOT)
        response = self.get_list(f"?form_id={self.plain_form.id}")
        row = response.json()["data"][0]
        self.assertEqual(sorted(row.keys()), LIST_ROW_KEYS)
        self.assertNotIn(b"geometry", response.content)

    def test_no_geometry_key_without_form_id(self):
        response = self.get_list()
        for row in response.json()["data"]:
            self.assertEqual(sorted(row.keys()), LIST_ROW_KEYS)
        self.assertNotIn(b"geometry", response.content)

    def test_datapoint_without_a_polygon_gets_an_empty_list(self):
        """Empty list means no polygon. An absent key would mean geometry
        is not being served at all. The device must tell them apart."""
        self.make_datapoint(self.form, "Plot B", None)
        response = self.get_list(f"?form_id={self.form.id}")
        rows = {r["name"]: r for r in response.json()["data"]}
        self.assertEqual(rows["Plot B"]["geometry"], [])
        self.assertEqual(len(rows["Plot A"]["geometry"]), 1)

    def test_stored_empty_list_is_excluded_from_payload_and_count(self):
        """A stored `options == []` is JSON '[]', not SQL NULL, so a
        naive `options__isnull=True` filter alone would leave it in the
        count while the payload loop drops it - a permanent mismatch
        the device could never reconcile. Both paths must agree, by
        construction: geometry_answers is the query the count will be
        built on (Task 6), and the payload is built from the same call.
        """
        empty = self.make_datapoint(self.form, "Plot Empty", [])
        response = self.get_list(f"?form_id={self.form.id}")
        rows = {r["name"]: r for r in response.json()["data"]}
        self.assertEqual(rows["Plot Empty"]["geometry"], [])

        self.assertEqual(
            geometry_answers(
                [empty.id], [self.form.plot_question.id]
            ).count(),
            0,
        )

    def test_repeat_group_answers_produce_multiple_entries(self):
        """One entry per geoshape ANSWER, not per datapoint. A singular
        object would silently drop everything past the first."""
        other = [[1.0, 2.0], [1.1, 2.0], [1.1, 2.1]]
        Answers.objects.create(
            data=self.datapoint, question=self.form.plot_question,
            options=other, created_by=self.user, index=1,
        )
        response = self.get_list(f"?form_id={self.form.id}")
        geometry = response.json()["data"][0]["geometry"]
        self.assertEqual(len(geometry), 2)
        self.assertEqual({g["index"] for g in geometry}, {0, 1})

    def test_the_gate_rejects_anything_that_is_not_exactly_true(self):
        """GEO-010 has not validated geoConfig yet and the editor
        array-wraps values, so "true" and ["true"] both reach here.
        Failing open would let the device trust a set nobody promised."""
        for bad in ["true", ["true"], 1, "True"]:
            with self.subTest(value=bad):
                self.form.plot_question.extra = {
                    "geoConfig": {"detectOverlaps": bad}
                }
                self.form.plot_question.save()
                response = self.get_list(f"?form_id={self.form.id}")
                self.assertNotIn(b"geometry", response.content)

    # ---------------------------------------------------------------
    # The completeness invariant
    #
    # `total` is the cursor-filtered delta. `geometry_total` is the
    # absolute candidate count. They are deliberately different
    # numbers. These used to live in a subclass of this class, which
    # made Django's loader re-collect every test above them a second
    # time and pay the seeder fixture twice for it.
    # ---------------------------------------------------------------

    def test_geometry_total_counts_every_candidate(self):
        self.make_datapoint(self.form, "Plot B", ADDIS_PLOT)
        response = self.get_list(f"?form_id={self.form.id}")
        self.assertEqual(response.json()["geometry_total"], 2)

    def test_geometry_total_ignores_the_sync_cursor(self):
        """The whole point. A device that has already synced sees a delta
        of zero rows and still learns there are two candidates it must be
        holding before it may trust a no-overlap result."""
        self.make_datapoint(self.form, "Plot B", ADDIS_PLOT)
        self.assignment.last_synced_at = timezone.now()
        self.assignment.save()
        response = self.get_list(f"?form_id={self.form.id}")
        body = response.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["geometry_total"], 2)

    def test_geometry_total_is_the_same_on_every_page(self):
        for n in range(3):
            self.make_datapoint(self.form, f"Plot P{n}", ADDIS_PLOT)
        first = self.get_list(f"?form_id={self.form.id}&page_size=2&page=1")
        second = self.get_list(f"?form_id={self.form.id}&page_size=2&page=2")
        self.assertEqual(first.json()["geometry_total"], 4)
        self.assertEqual(second.json()["geometry_total"], 4)

    def test_geometry_total_counts_answers_not_datapoints(self):
        """One row per geoshape answer, matching GEO-006's index, so the
        device's COUNT(*) and this number describe the same unit."""
        other = [[1.0, 2.0], [1.1, 2.0], [1.1, 2.1]]
        Answers.objects.create(
            data=self.datapoint, question=self.form.plot_question,
            options=other, created_by=self.user, index=1,
        )
        response = self.get_list(f"?form_id={self.form.id}")
        self.assertEqual(response.json()["geometry_total"], 2)

    def test_geometry_full_returns_the_whole_set(self):
        """The repair path. After a count mismatch the device re-lists
        without the cursor and rebuilds its index."""
        self.make_datapoint(self.form, "Plot B", ADDIS_PLOT)
        self.assignment.last_synced_at = timezone.now()
        self.assignment.save()
        delta = self.get_list(f"?form_id={self.form.id}")
        full = self.get_list(f"?form_id={self.form.id}&geometry_full=true")
        self.assertEqual(delta.json()["total"], 0)
        self.assertEqual(full.json()["total"], 2)
        self.assertEqual(len(full.json()["data"]), 2)

    def test_no_geometry_total_when_the_flag_is_off(self):
        self.make_datapoint(self.plain_form, "Plain A", ADDIS_PLOT)
        response = self.get_list(f"?form_id={self.plain_form.id}")
        self.assertNotIn("geometry_total", response.json())

    def test_no_geometry_total_without_form_id(self):
        response = self.get_list()
        self.assertNotIn("geometry_total", response.json())

    def test_geometry_full_without_form_id_is_ignored(self):
        """There is no geometry on that path to make full."""
        response = self.get_list("?geometry_full=true")
        self.assertNotIn("geometry_total", response.json())
        self.assertNotIn(b"geometry", response.content)

    def test_the_count_and_the_payload_describe_the_same_set(self):
        """If these ever disagree the device's comparison never balances
        and it refuses to validate forever."""
        self.make_datapoint(self.form, "Plot B", ADDIS_PLOT)
        response = self.get_list(f"?form_id={self.form.id}&geometry_full=true")
        body = response.json()
        served = sum(len(row["geometry"]) for row in body["data"])
        self.assertEqual(served, body["geometry_total"])
