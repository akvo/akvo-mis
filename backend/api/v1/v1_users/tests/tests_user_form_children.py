"""Assigning a registration form to a user assigns its monitoring forms.

The user screen's picker offers registration forms only -- AddUser.jsx
filters on `!f?.content?.parent` -- so `forms` in a POST/PUT payload can
never name a monitoring form. The API took the list literally, which left
users assigned to a parent and none of its children.

That is load-bearing rather than cosmetic: `UserSerializer.get_forms`
returns `user_form.all()` verbatim, and the mobile assignment screen
reads monitoring forms out of that same list as the children of each
registration form. A parent with no assigned children offers nothing to
attach to a device.

The PUT is also destructive -- `update()` deletes every UserForms row and
recreates from the payload -- so editing a user through the UI could undo
a correct assignment made anywhere else.
"""
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes
from api.v1.v1_forms.models import Forms, UserForms
from api.v1.v1_users.models import Organisation, SystemUser


@override_settings(USE_TZ=False, TEST_ENV=True)
class AssignedFormsIncludeMonitoringChildrenTest(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("fake_organisation_seeder")
        call_command("form_seeder", "--test")
        login = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.header = {
            "HTTP_AUTHORIZATION": f"Bearer {login.json().get('token')}"
        }
        self.org = Organisation.objects.order_by("?").first()

        self.parent = (
            Forms.objects.filter(
                type=FormTypes.registration,
                children__isnull=False,
                status=FormStatus.published,
            )
            .distinct()
            .first()
        )
        self.assertIsNotNone(
            self.parent, "fixture has no registration form with children"
        )
        self.children = set(
            Forms.objects.filter(
                parent=self.parent, status=FormStatus.published
            ).values_list("id", flat=True)
        )
        self.assertTrue(self.children)

    def assigned_ids(self, email):
        user = SystemUser.objects.get(email=email)
        return set(
            UserForms.objects.filter(user=user).values_list(
                "form_id", flat=True
            )
        )

    def payload(self, email, forms, superuser=False):
        return {
            "email": email,
            "password": "Test105*",
            "first_name": "Child",
            "last_name": "Forms",
            "is_superuser": superuser,
            "organisation": self.org.id,
            "forms": forms,
            "roles": [],
        }

    def post(self, email, forms, superuser=False):
        response = self.client.post(
            "/api/v1/user",
            self.payload(email, forms, superuser),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return SystemUser.objects.get(email=email)

    def test_create_assigns_the_monitoring_children(self):
        self.post("child@test.com", [self.parent.id])

        assigned = self.assigned_ids("child@test.com")
        self.assertIn(self.parent.id, assigned)
        self.assertTrue(
            self.children <= assigned,
            f"children {self.children - assigned} were not assigned",
        )

    def test_update_assigns_the_monitoring_children(self):
        """The PUT the control centre sends carries only parent ids.

        This is the exact shape of the request that exposed the gap:
        `"forms": [<registration id>, <registration id>]`.
        """
        user = self.post("update@test.com", [])

        response = self.client.put(
            f"/api/v1/user/{user.id}",
            self.payload("update@test.com", [self.parent.id]),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(response.status_code, 200, response.content)

        assigned = self.assigned_ids("update@test.com")
        self.assertIn(self.parent.id, assigned)
        self.assertTrue(
            self.children <= assigned,
            f"children {self.children - assigned} were not assigned",
        )

    def test_a_draft_child_is_not_assigned(self):
        draft_child = Forms.objects.create(
            name="Draft child",
            version=1,
            parent=self.parent,
            type=FormTypes.monitoring,
            status=FormStatus.draft,
        )

        self.post("draft@test.com", [self.parent.id])

        self.assertNotIn(draft_child.id, self.assigned_ids("draft@test.com"))

    def test_an_unrelated_registration_form_is_not_assigned(self):
        other = (
            Forms.objects.filter(
                type=FormTypes.registration, status=FormStatus.published
            )
            .exclude(pk=self.parent.pk)
            .first()
        )
        self.assertIsNotNone(other)

        self.post("unrelated@test.com", [self.parent.id])

        self.assertNotIn(other.id, self.assigned_ids("unrelated@test.com"))

    def test_no_duplicate_rows(self):
        user = self.post("dupe@test.com", [self.parent.id])

        rows = list(
            UserForms.objects.filter(user=user).values_list(
                "form_id", flat=True
            )
        )
        self.assertEqual(len(rows), len(set(rows)))

    def test_superuser_with_no_forms_still_gets_everything_published(self):
        """The pre-existing branch must keep working unchanged."""
        self.post("super9@test.com", [], superuser=True)

        self.assertEqual(
            self.assigned_ids("super9@test.com"),
            set(
                Forms.objects.filter(
                    status=FormStatus.published
                ).values_list("id", flat=True)
            ),
        )
