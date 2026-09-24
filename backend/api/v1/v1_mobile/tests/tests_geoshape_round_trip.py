from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import FormStatus, QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser


# Ethiopia, not the Indian Ocean. Asymmetric on purpose: an axis swap
# here fails the equality assertion instead of passing on lookalike
# numbers.
ADDIS_PLOT = [[9.03, 38.74], [9.04, 38.74], [9.04, 38.75], [9.03, 38.75]]
MOVED_PLOT = [[9.05, 38.76], [9.06, 38.76], [9.06, 38.77]]


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeoshapeRoundTripTestCase(TestCase):
    """A polygon must survive submit, storage and sync unchanged.

    Before this branch it could not be submitted at all: geoshape was in
    no branch of the answer dispatch, so the coordinates were assigned to
    `Answers.value`, a FloatField, and the write failed. Nothing noticed
    because no client had ever sent one.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        login = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.token = login.json().get("token")
        self.user = SystemUser.objects.get(email="admin@akvo.org")

        self.root = Administration.objects.filter(parent__isnull=True).first()
        self.child = self.root.parent_administration.first()

        self.form = Forms.objects.create(
            name="Plot Form", version=1, status=FormStatus.published
        )
        group = QuestionGroup.objects.create(
            form=self.form, name="Group", order=1
        )
        self.plot_q = Questions.objects.create(
            form=self.form, question_group=group, name="plot",
            label="Plot boundary", order=1,
            type=QuestionTypes.geoshape,
            extra={"geoConfig": {"detectOverlaps": True}},
        )
        self.user.user_form.create(form=self.form)

        self.assignment = MobileAssignment.objects.create_assignment(
            user=self.user, name="device"
        )
        self.assignment.administrations.add(self.child)
        self.assignment.forms.add(self.form)

    def submit(self, coordinates):
        return self.client.post(
            f"/api/v1/form-pending-data/{self.form.id}",
            {
                "data": {
                    "name": "Plot A",
                    "administration": self.child.id,
                    "geo": [9.03, 38.74],
                },
                "answer": [
                    {"question": self.plot_q.id, "value": coordinates}
                ],
            },
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )

    def device_list(self):
        token = MobileAssignmentToken.for_assignment(self.assignment)
        return self.client.get(
            f"/api/v1/device/datapoint-list/?form_id={self.form.id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

    def test_a_submitted_polygon_reaches_the_device_unchanged(self):
        submitted = self.submit(ADDIS_PLOT)
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)

        stored = Answers.objects.get(question=self.plot_q)
        self.assertEqual(stored.options, ADDIS_PLOT)
        self.assertIsNone(stored.value)
        self.assertIsNone(stored.name)

        listed = self.device_list()
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        body = listed.json()
        geometry = body["data"][0]["geometry"][0]
        self.assertEqual(geometry["coordinates"], ADDIS_PLOT)
        self.assertEqual(geometry["question_id"], self.plot_q.id)
        self.assertEqual(geometry["bbox"], {
            "min_lat": 9.03, "max_lat": 9.04,
            "min_lon": 38.74, "max_lon": 38.75,
        })
        self.assertEqual(body["geometry_total"], 1)

    def test_the_ring_is_not_closed_and_nothing_is_rounded(self):
        """Storage is verbatim. No GeoJSON wrapper, no repeated first
        vertex, no reduced precision. Every one of those would put the
        device's copy and the server's copy subtly out of step."""
        self.submit(ADDIS_PLOT)
        coordinates = self.device_list().json()[
            "data"][0]["geometry"][0]["coordinates"]
        self.assertEqual(coordinates, ADDIS_PLOT)
        self.assertEqual(len(coordinates), 4)
        self.assertNotEqual(coordinates[0], coordinates[-1])
        self.assertEqual(coordinates[0][0], 9.03)

    def test_editing_a_polygon_keeps_it_in_options(self):
        """The edit path shares `answer_fields` with the create path as
        of Task 2, so a polygon must not regress to `value` on edit."""
        self.submit(ADDIS_PLOT)
        datapoint = FormData.objects.get(form=self.form)
        response = self.client.put(
            f"/api/v1/form-data/{self.form.id}?data_id={datapoint.id}",
            [{"question": self.plot_q.id, "value": MOVED_PLOT}],
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stored = Answers.objects.get(question=self.plot_q)
        self.assertEqual(stored.options, MOVED_PLOT)
        self.assertIsNone(stored.value)

        geometry = self.device_list().json()[
            "data"][0]["geometry"][0]
        self.assertEqual(geometry["coordinates"], MOVED_PLOT)
        self.assertEqual(geometry["bbox"]["max_lat"], 9.06)

    def test_a_string_polygon_is_rejected_at_the_api(self):
        response = self.submit("9.03,38.74")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
