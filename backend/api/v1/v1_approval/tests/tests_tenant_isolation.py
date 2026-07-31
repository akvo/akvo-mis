from django.test.utils import override_settings

from api.v1.v1_approval.models import DataBatch
from utils.tenant_test_case import TenantIsolationTestCase

# Every batch endpoint takes an id straight from the URL.
BATCH_PATHS = [
    "form-pending-data-batch",
    "batch/comment",
    "batch/summary",
]


@override_settings(USE_TZ=False)
class ApprovalTenantIsolationTestCase(TenantIsolationTestCase):
    """Batch ids are sequential, so anything that fetches one without asking
    whose it is hands a workspace's pending submissions to whoever guesses
    the number — a leak no queryset-level filtering can catch, because the
    lookup never goes through a list.
    """

    def make_tenant(self, sub):
        tenant = super().make_tenant(sub)
        tenant["batch"] = DataBatch.objects.create(
            form=tenant["form"],
            administration=tenant["child"],
            user=tenant["user"],
            name=f"{sub}-batch",
        )
        return tenant

    def get_batch(self, path, fixture):
        return self.client.get(
            f"/api/v1/{path}/{fixture['batch'].id}",
            **self.auth(self.a["user"]),
        )

    def test_another_tenants_batch_is_not_found(self):
        for path in BATCH_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.get_batch(path, self.b).status_code, 404)

    def test_your_own_batch_is_served(self):
        # The counterpart to the refusals above: a route that does not exist
        # answers 404 too, so those only mean something next to this.
        for path in BATCH_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.get_batch(path, self.a).status_code, 200)
