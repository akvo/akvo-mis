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
# A different continent, deliberately: if acme's response ever carried
# beta's coordinates, a substring or list-membership check on this
# constant fails loudly, where a second ADDIS_PLOT-shaped polygon could
# leak silently and still pass an assertion that only looks at counts.
TOKYO_PLOT = [
    [35.65, 139.83], [35.66, 139.83], [35.66, 139.84], [35.65, 139.84]
]
TENANT_PLOTS = {"acme": ADDIS_PLOT, "beta": TOKYO_PLOT}


@override_settings(USE_TZ=False, TEST_ENV=True)
class GeometryTenantIsolationTestCase(TenantIsolationTestCase):
    """Geometry is a new bulk field, which is an easy place to leak.

    `Answers.objects` is not tenant-scoped on its own: `TenantManager`
    leaves `get_queryset` alone. These tests prove a tenant never sees
    another tenant's rows, counts, or coordinates.

    They cannot pin the `data_id__in` half of the scoping in
    `geometry_answers`: dropping it and keeping only `question_id__in`
    would still pass here, because question ids come from one global
    sequence and each `Questions` row is FK-chained to exactly one
    tenant's form, so tenant A's query would still match only its own
    row even with that filter gone. `GeometryAssignmentScopingTestCase`
    below is what pins `data_id__in` -- its "mine" and "theirs"
    datapoints deliberately share one `Questions` row, so dropping that
    filter there genuinely diverges.
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
        plot = TENANT_PLOTS[sub]
        datapoint = FormData.objects.create(
            name=f"{sub}-plot", form=tenant["form"],
            administration=tenant["child"], created_by=tenant["user"],
            uuid=f"uuid-{sub}",
        )
        Answers.objects.create(
            data=datapoint, question=tenant["question"],
            options=plot, created_by=tenant["user"],
        )
        tenant["datapoint"] = datapoint
        # Beta gets a second polygon so the fixture is asymmetric.
        # With one polygon each, a tenant swap -- or a scoping
        # regression that drops tenant filtering entirely -- would
        # still leave both tenants seeing "1" and every assertion
        # below would still pass. Two different totals (1 vs 2) means
        # a swap or an unfiltered count both produce a number that
        # does not match either expectation.
        if sub == "beta":
            second = FormData.objects.create(
                name=f"{sub}-plot-2", form=tenant["form"],
                administration=tenant["child"], created_by=tenant["user"],
                uuid=f"uuid-{sub}-2",
            )
            Answers.objects.create(
                data=second, question=tenant["question"],
                options=plot, created_by=tenant["user"],
            )
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
        """Acme has one polygon, beta has two. Counts must not match."""
        response_a = self.device_list(
            self.a, f"?form_id={self.a['form'].id}"
        )
        response_b = self.device_list(
            self.b, f"?form_id={self.b['form'].id}"
        )
        self.assertEqual(response_a.json()["geometry_total"], 1)
        self.assertEqual(response_b.json()["geometry_total"], 2)

    def test_the_payload_carries_only_this_tenants_polygons(self):
        response = self.device_list(self.a, f"?form_id={self.a['form'].id}")
        rows = response.json()["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "acme-plot")
        self.assertEqual(len(rows[0]["geometry"]), 1)
        # GEO-006 dropped coordinates; bbox is the tenant-specific fingerprint.
        acme_bbox = rows[0]["geometry"][0]["bbox"]
        self.assertEqual(acme_bbox, {
            "min_lat": 9.03, "max_lat": 9.04,
            "min_lon": 38.74, "max_lon": 38.75,
        })
        tokyo_bbox = {
            "min_lat": 35.65, "max_lat": 35.66,
            "min_lon": 139.83, "max_lon": 139.84,
        }
        self.assertNotEqual(acme_bbox, tokyo_bbox)
        self.assertNotIn(b"beta", response.content)

        response_b = self.device_list(
            self.b, f"?form_id={self.b['form'].id}"
        )
        rows_b = response_b.json()["data"]
        self.assertEqual(len(rows_b), 2)
        beta_bboxes = [
            entry["bbox"] for row in rows_b for entry in row["geometry"]
        ]
        self.assertEqual(beta_bboxes, [tokyo_bbox, tokyo_bbox])
        self.assertNotIn(acme_bbox, beta_bboxes)
        self.assertNotIn(b"acme", response_b.content)


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
