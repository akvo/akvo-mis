import uuid

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormDataListAdministrationScopeTest(TestCase, ProfileTestHelperMixin):
    """A client-supplied `administration` filter must never widen access.

    Before the fix, supplying `administration=<ancestor>` bypassed the
    requesting user's own administration scope entirely (the user-scope
    filter lived only in the else branch), so a province-scoped user could
    read the whole country's data by passing the national root id.
    """

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.form = Forms.objects.get(pk=1)
        self.root = Administration.objects.get(level__level=0)
        level1 = list(
            Administration.objects.filter(level__level=1).order_by("id")
        )
        self.adm_in = level1[0]
        self.adm_out = level1[1]

        # Author the fixtures as a superuser; the scoped user below only reads.
        self.author = self.create_user(
            email="author@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        self.dp_in = self._make_datapoint(self.adm_in, "InScope DP")
        self.dp_out = self._make_datapoint(self.adm_out, "OutOfScope DP")

        # A user whose only role is at adm_in, assigned to the form.
        self.user = self.create_user(
            email="scoped@akvo.org",
            role_level=self.IS_ADMIN,
            administration=self.adm_in,
            form=self.form,
        )
        self.user.set_password("test")
        self.user.save()
        self.token = self.get_auth_token(self.user.email, "test")

    def _make_datapoint(self, administration, name):
        dp = self.form.form_form_data.create(
            name=name,
            administration=administration,
            geo=[0.0, 0.0],
            created_by=self.author,
            updated_by=self.author,
            is_pending=False,
        )
        add_fake_answers(dp)
        return dp

    def _list_ids(self, query=""):
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}{query}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        return [item["id"] for item in response.json()["data"]]

    def test_ancestor_administration_does_not_leak_out_of_scope(self):
        # Passing the national root (an ancestor of the user's province) must
        # still be clamped to the user's own subtree.
        ids = self._list_ids(f"?administration={self.root.id}")
        self.assertIn(self.dp_in.id, ids)
        self.assertNotIn(self.dp_out.id, ids)

    def test_sibling_administration_returns_nothing(self):
        # The user has no access to adm_out, so filtering by it yields nothing.
        ids = self._list_ids(f"?administration={self.adm_out.id}")
        self.assertNotIn(self.dp_out.id, ids)
        self.assertNotIn(self.dp_in.id, ids)

    def test_default_scope_excludes_out_of_scope(self):
        ids = self._list_ids()
        self.assertIn(self.dp_in.id, ids)
        self.assertNotIn(self.dp_out.id, ids)

    def test_superuser_is_unrestricted(self):
        self.author.set_password("test")
        self.author.save()
        token = self.get_auth_token(self.author.email, "test")
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}?administration={self.root.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["data"]]
        self.assertIn(self.dp_in.id, ids)
        self.assertIn(self.dp_out.id, ids)

    def _make_monitoring(self, administration, shared_uuid, name):
        child_form = self.form.children.first()
        self.assertIsNotNone(child_form)
        dp = child_form.form_form_data.create(
            name=name,
            administration=administration,
            geo=[0.0, 0.0],
            uuid=shared_uuid,
            created_by=self.author,
            updated_by=self.author,
            is_pending=False,
        )
        add_fake_answers(dp)
        return child_form, dp

    def _list_parent(self, child_form, shared_uuid):
        response = self.client.get(
            f"/api/v1/form-data/{child_form.id}?parent={shared_uuid}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        return [item["id"] for item in response.json()["data"]]

    def test_parent_filter_excludes_out_of_scope_monitoring(self):
        # A client-supplied parent uuid must not expose another
        # administration's monitoring submissions.
        shared_uuid = str(uuid.uuid4())
        child_form, mon = self._make_monitoring(
            self.adm_out, shared_uuid, "OutOfScope monitoring"
        )
        self.assertNotIn(mon.id, self._list_parent(child_form, shared_uuid))

    def test_parent_filter_includes_in_scope_monitoring(self):
        shared_uuid = str(uuid.uuid4())
        child_form, mon = self._make_monitoring(
            self.adm_in, shared_uuid, "InScope monitoring"
        )
        self.assertIn(mon.id, self._list_parent(child_form, shared_uuid))
