from django.test import TestCase

from api.v1.v1_mobile.authentication import MobileAssignmentToken
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.tests.mixins import TenantTestHelperMixin


class MobileDeactivationCascadeTestCase(TestCase, TenantTestHelperMixin):
    """Deactivating a person stops their devices syncing.

    Already true for is_active, which IsMobileAssignment has always
    checked. Not true for a soft delete, which is the gap this closes:
    a deleted user's device kept syncing indefinitely.
    """

    def setUp(self):
        self.acme = self.create_tenant("acme", ["Country"], "Kenya")
        self.assignment = MobileAssignment.objects.create_assignment(
            user=self.acme.admin, name="device-1"
        )
        token = MobileAssignmentToken.for_assignment(self.assignment)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def sync(self):
        # A parameterless GET behind IsMobileAssignment. `/device/auth`
        # is not one: it is the POST that exchanges a passcode for a
        # token, and runs before there is an assignment to check.
        return self.client.get("/api/v1/device/datapoint-list", **self.auth)

    def test_an_active_user_syncs(self):
        self.assertNotIn(self.sync().status_code, (401, 403))

    def test_a_deactivated_user_cannot_sync(self):
        self.acme.admin.is_active = False
        self.acme.admin.save(update_fields=["is_active"])
        self.assertEqual(self.sync().status_code, 403)

    def test_a_soft_deleted_user_cannot_sync(self):
        # The gap. IsMobileAssignment consulted is_active but not
        # deleted_at, so a deleted account's device kept syncing.
        self.acme.admin.soft_delete()
        self.assertEqual(self.sync().status_code, 403)

    def test_reactivation_restores_sync(self):
        self.acme.admin.is_active = False
        self.acme.admin.save(update_fields=["is_active"])
        self.acme.admin.is_active = True
        self.acme.admin.save(update_fields=["is_active"])
        self.assertNotIn(self.sync().status_code, (401, 403))
