from django.test.utils import override_settings
from rest_framework import status

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import QuestionGroup, Questions
from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration
from utils.tenant_test_case import TenantIsolationTestCase


ADDIS_PLOT = [[9.03, 38.74], [9.04, 38.74], [9.04, 38.75], [9.03, 38.75]]


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeometryTenantIsolationTestCase(TenantIsolationTestCase):
    """Geometry is a new bulk field, which is an easy place to leak.

    `Answers.objects` is not tenant-scoped on its own: `TenantManager`
    leaves `get_queryset` alone. The only thing keeping tenant B's
    polygons out of tenant A's response is that the ids come from
    `FormData.objects.for_user()`. These tests are what proves it.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        group = QuestionGroup.objects.create(
            form=tenant["form"], name="Group", order=1
        )
        tenant["question"] = Questions.objects.create(
            form=tenant["form"], question_group=group, name="plot",
            label="Plot boundary", order=1,
            type=QuestionTypes.geoshape,
            extra={"geoConfig": {"detectOverlaps": True}},
        )
        datapoint = FormData.objects.create(
            name=f"{sub}-plot", form=tenant["form"],
            administration=tenant["child"], created_by=tenant["user"],
            uuid=f"uuid-{sub}",
        )
        Answers.objects.create(
            data=datapoint, question=tenant["question"],
            options=ADDIS_PLOT, created_by=tenant["user"],
        )
        tenant["datapoint"] = datapoint
        assignment = MobileAssignment.objects.create_assignment(
            user=tenant["user"], name=f"{sub}-device"
        )
        assignment.administrations.add(tenant["child"])
        assignment.forms.add(tenant["form"])
        tenant["assignment"] = assignment
        return tenant

    def device_list(self, tenant, query=""):
        token = MobileAssignmentToken.for_assignment(tenant["assignment"])
        return self.client.get(
            f"/api/v1/device/datapoint-list/{query}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )

    def test_a_device_cannot_request_another_tenants_form(self):
        response = self.device_list(
            self.a, f"?form_id={self.b['form'].id}"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_geometry_total_counts_only_this_tenants_candidates(self):
        """Two tenants, one polygon each. Each must see exactly one."""
        for tenant in (self.a, self.b):
            response = self.device_list(
                tenant, f"?form_id={tenant['form'].id}"
            )
            self.assertEqual(response.json()["geometry_total"], 1)

    def test_the_payload_carries_only_this_tenants_polygons(self):
        response = self.device_list(self.a, f"?form_id={self.a['form'].id}")
        rows = response.json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "acme-plot")
        self.assertNotIn(b"beta", response.content)


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeometryAssignmentScopingTestCase(TenantIsolationTestCase):
    """Within one tenant, an enumerator sees only their administrations.

    A datapoint they could not already see must not become visible just
    because it carries a polygon.
    """

    def setUp(self):
        super().setUp()
        tenant = self.a
        group = QuestionGroup.objects.create(
            form=tenant["form"], name="Group", order=1
        )
        self.question = Questions.objects.create(
            form=tenant["form"], question_group=group, name="plot",
            label="Plot boundary", order=1,
            type=QuestionTypes.geoshape,
            extra={"geoConfig": {"detectOverlaps": True}},
        )
        self.other_child = Administration.objects.create(
            parent=tenant["root"], level=tenant["child_level"],
            name="acme-d2", tenant=tenant["tenant"],
        )
        for administration, name in (
            (tenant["child"], "mine"),
            (self.other_child, "theirs"),
        ):
            datapoint = FormData.objects.create(
                name=name, form=tenant["form"],
                administration=administration, created_by=tenant["user"],
                uuid=f"uuid-{name}",
            )
            Answers.objects.create(
                data=datapoint, question=self.question,
                options=ADDIS_PLOT, created_by=tenant["user"],
            )
        self.assignment = MobileAssignment.objects.create_assignment(
            user=tenant["user"], name="acme-device"
        )
        self.assignment.administrations.add(tenant["child"])
        self.assignment.forms.add(tenant["form"])

    def test_geometry_total_respects_the_assignment(self):
        token = MobileAssignmentToken.for_assignment(self.assignment)
        response = self.client.get(
            f"/api/v1/device/datapoint-list/?form_id={self.a['form'].id}",
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        body = response.json()
        self.assertEqual(body["geometry_total"], 1)
        self.assertEqual([r["name"] for r in body["data"]], ["mine"])
        self.assertNotIn(b"theirs", response.content)
