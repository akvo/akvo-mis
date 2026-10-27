import typing
from django.core.management import call_command
from django.http import HttpResponse
from django.test import TestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False)
class SuperadminRootMobileUsersTestCase(TestCase, ProfileTestHelperMixin):
    """A superadmin must see mobile users created by another superadmin,
    including assignments pinned to the root administration (whose path
    is NULL and so is missed by a bare path__startswith filter).
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.form = Forms.objects.get(pk=1)
        self.root = Administration.objects.get(parent__isnull=True)
        self.child = Administration.objects.filter(
            level__level__gt=0
        ).first()
        self.super1 = self.create_user(
            email="super1@akvo.org", role_level=self.IS_SUPER_ADMIN,
        )
        self.super2 = self.create_user(
            email="super2@akvo.org", role_level=self.IS_SUPER_ADMIN,
        )

    def _create_assignment(self, user, name, administration):
        token = RefreshToken.for_user(user).access_token
        return typing.cast(
            HttpResponse,
            self.client.post(
                "/api/v1/mobile-assignments",
                {
                    "name": name,
                    "forms": [self.form.id],
                    "administrations": [administration.id],
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )

    def _list_names(self, user):
        token = RefreshToken.for_user(user).access_token
        response = typing.cast(
            HttpResponse,
            self.client.get(
                "/api/v1/mobile-assignments",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertEqual(response.status_code, 200)
        return [row["name"] for row in response.json()["data"]]

    def test_superadmin_sees_root_pinned_assignment_of_other_superadmin(self):
        # super2 creates an assignment pinned to the root administration
        res = self._create_assignment(
            self.super2, "super2.root.mobile", self.root
        )
        self.assertEqual(res.status_code, 201)

        # super1 (a different superadmin) must see it
        self.assertIn("super2.root.mobile", self._list_names(self.super1))

    def test_superadmin_still_sees_descendant_assignment(self):
        # Guard the existing path__startswith branch against the OR change
        res = self._create_assignment(
            self.super2, "super2.child.mobile", self.child
        )
        self.assertEqual(res.status_code, 201)

        self.assertIn("super2.child.mobile", self._list_names(self.super1))
