from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant


@override_settings(USE_TZ=False)
class MobileTenantIsolationTestCase(TestCase):
    def _tenant(self, sub):
        tenant = Tenant.objects.create(subdomain=sub)
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        child_level = Levels.objects.create(
            name="district", level=1, tenant=tenant
        )
        root = Administration.objects.create(
            parent=None, level=level, name=sub, tenant=tenant
        )
        child = Administration.objects.create(
            parent=root, level=child_level, name=f"{sub}-d", tenant=tenant
        )
        user = SystemUser.objects.create_superuser(
            email=f"admin@{sub}.org", password="Secret#Pass123",
            first_name="A", last_name="A", tenant=tenant,
        )
        form = Forms.objects.create(name=f"{sub}-form", tenant=tenant)
        data = FormData.objects.create(
            name=f"{sub}-dp", form=form, administration=child,
            created_by=user,
        )
        assignment = MobileAssignment.objects.create_assignment(
            user=user, name=f"{sub}-device"
        )
        assignment.administrations.add(child)
        assignment.forms.add(form)
        return {
            "tenant": tenant, "user": user, "form": form, "data": data,
            "assignment": assignment,
        }

    def _auth(self, user):
        return {
            "HTTP_AUTHORIZATION":
                f"Bearer {RefreshToken.for_user(user).access_token}"
        }

    def setUp(self):
        self.a = self._tenant("acme")
        self.b = self._tenant("beta")

    def test_mobile_assignment_list_excludes_other_tenant(self):
        res = self.client.get(
            "/api/v1/mobile-assignments", **self._auth(self.a["user"])
        )
        self.assertEqual(res.status_code, 200)
        names = [m["name"] for m in res.json()["data"]]
        self.assertIn(self.a["assignment"].name, names)
        self.assertNotIn(self.b["assignment"].name, names)

    def test_datapoint_detail_404_on_foreign_object(self):
        res = self.client.get(
            f"/api/v1/maps/datapoint/{self.b['data'].id}",
            **self._auth(self.a["user"]),
        )
        self.assertEqual(res.status_code, 404)
