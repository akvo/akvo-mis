import typing
from django.core.management import call_command
from django.http import HttpResponse
from django.test import TestCase, override_settings
from api.v1.v1_forms.models import Forms
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_profile.models import (
    Administration,
    EntityData,
    Entity
)

from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from utils.custom_helper import CustomPasscode


@override_settings(USE_TZ=False)
class MobileAssignmentTestCase(TestCase, ProfileTestHelperMixin):

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command('form_seeder', '--test')
        call_command("entities_seeder", "--test", True)
        call_command("default_roles_seeder", "--test", 1)

        for entity in Entity.objects.all():
            for adm in Administration.objects.filter(
                    parent__isnull=False
            ).all():
                EntityData.objects.create(
                    entity=entity,
                    administration=adm,
                    name=f"{entity.name} - {adm.name}"
                )
        self.user = self.create_user('test@akvo.org', self.IS_ADMIN)
        self.token = self.get_auth_token(self.user.email)

    def test_list(self):
        adm1 = Administration.objects.first()
        adm2 = Administration.objects.all()[1]
        adm3 = Administration.objects.last()
        form1 = Forms.objects.first()
        form2 = Forms.objects.last()
        assignment1 = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #1')
        assignment1.forms.add(form1)
        assignment1.administrations.add(adm1, adm2)
        assignment2 = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #2')
        assignment2.forms.add(form2)
        assignment2.administrations.add(adm1, adm3)

        response = typing.cast(
                HttpResponse,
                self.client.get(
                    '/api/v1/mobile-assignments',
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body['data']), 2)

    def test_list_shows_only_created_by_user(self):
        other_user = self.create_user('otheruser@akvo.org', self.IS_ADMIN)
        assignment1 = MobileAssignment.objects.create_assignment(
                user=other_user, name='assignment #1')
        assignment2 = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #2')
        assignment3 = MobileAssignment.objects.create_assignment(
                user=other_user, name='assignment #3')

        response = typing.cast(
                HttpResponse,
                self.client.get(
                    '/api/v1/mobile-assignments',
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        data = response.json().get('data')
        ids = [it['id'] for it in data]
        self.assertIn(assignment2.id, ids)
        self.assertNotIn(assignment1.id, ids)
        self.assertNotIn(assignment3.id, ids)

    def test_create(self):
        adm = Administration.objects.first()
        form = Forms.objects.first()
        payload = {
            'name': 'test assignment',
            'forms': [form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
                HttpResponse,
                self.client.post(
                    '/api/v1/mobile-assignments',
                    payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='test assignment')
        self.assertEqual(
                CustomPasscode().encode(data['passcode']), assignment.passcode)
        self.assertEqual(len(data['forms']), assignment.forms.count())
        self.assertEqual(
                len(data['administrations']),
                assignment.administrations.count())

    def test_update(self):
        assignment = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #1')
        adm = Administration.objects.first()
        form = Forms.objects.first()
        payload = {
            'name': 'renamed assignment',
            'forms': [form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
                HttpResponse,
                self.client.put(
                    f'/api/v1/mobile-assignments/{assignment.id}',
                    payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'renamed assignment')
        self.assertEqual(len(data['forms']), 1)
        self.assertEqual(len(data['administrations']), 1)

    def test_update_relations(self):
        adm1 = Administration.objects.filter(
            level__level=1
        ).order_by("?").first()
        [adm2, adm3] = Administration.objects.filter(
            path__startswith="{0}{1}".format(
                adm1.path, adm1.id
            )
        ).all()[:2]
        form1 = Forms.objects.get(pk=1)
        form2 = Forms.objects.get(pk=4)
        assignment = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #1')
        assignment.forms.add(form1)
        assignment.administrations.add(adm1, adm2)
        payload = {
            'name': assignment.name,
            'forms': [form2.id],
            'administrations': [adm2.id, adm3.id],
        }
        response = typing.cast(
                HttpResponse,
                self.client.put(
                    f'/api/v1/mobile-assignments/{assignment.id}',
                    payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([it['id'] for it in data['forms']], [form2.id])
        self.assertEqual(
                [it['id'] for it in data['administrations']],
                [adm2.id, adm3.id])

    def test_delete(self):
        adm1 = Administration.objects.first()
        adm2 = Administration.objects.all()[1]
        form1 = Forms.objects.first()
        assignment = MobileAssignment.objects.create_assignment(
                user=self.user, name='assignment #1')
        assignment.forms.add(form1)
        assignment.administrations.add(adm1, adm2)

        response = typing.cast(
                HttpResponse,
                self.client.delete(
                    f'/api/v1/mobile-assignments/{assignment.id}',
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 204)

    def test_create_error_entity_validation(self):
        adm = Administration.objects \
            .filter(entity_data__isnull=False).last()
        adm.entity_data.all().delete()
        form = Forms.objects.get(pk=2)
        payload = {
            'name': 'test assignment',
            'forms': [form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
                HttpResponse,
                self.client.post(
                    '/api/v1/mobile-assignments',
                    payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data, {
            'forms': [{
                'form': '2',
                'entity': 'School',
                'exists': 'True'
            }]})

    def test_create_success_entity_validation(self):
        entity = EntityData.objects.last()
        adm = entity.administration
        form = Forms.objects.get(pk=2)
        payload = {
            'name': 'secret',
            'forms': [form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
                HttpResponse,
                self.client.post(
                    '/api/v1/mobile-assignments',
                    payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='secret')
        self.assertEqual(
                CustomPasscode().encode(data['passcode']), assignment.passcode)
        self.assertEqual(data['forms'], [{
            'id': form.id,
            'name': form.name,
            'type': 'registration'
        }])
        self.assertEqual(
                len(data['administrations']),
                assignment.administrations.count())

    def test_list_with_superuser(self):
        # Create mobile assignments for testing
        parent_adm = Administration.objects.filter(
            level__level=3
        ).order_by("?").first()
        form = Forms.objects.get(pk=1)
        for adm in parent_adm.parent_administration.all():
            mobile = MobileAssignment.objects.create_assignment(
                user=self.user, name=f'Assignment for {adm.name}'
            )
            mobile.administrations.add(adm)
            mobile.forms.add(form)
        superuser = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN
        )
        superuser.set_password("password")
        superuser.save()

        super_token = self.get_auth_token(superuser.email, "password")
        response = self.client.get(
            '/api/v1/mobile-assignments',
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {super_token}'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json().get('data')
        self.assertTrue(len(data) > 0, "Superuser should see all assignments")

    def test_list_with_admin_and_exclude_diff_administration(self):
        # Get a form for testing
        form = Forms.objects.get(pk=1)

        # Create mobile assignments for 2 different administrations
        [parent1, parent2] = Administration.objects.filter(
            level__level=1
        ).order_by("?").all()[:2]

        # Create a new administration for testing
        admin_user = self.create_user(
            email="admin.123@test.com",
            role_level=self.IS_ADMIN,
            administration=parent1,
            form=form
        )
        admin_user.set_password("password")
        admin_user.save()

        # Verify the admin user have administration and forms
        self.assertIn(
            parent1.name,
            [
                ur.administration.name
                for ur in admin_user.user_user_role.all()
            ]
        )

        admin_token = self.get_auth_token(admin_user.email, "password")

        # Create assignments for both administrations
        child_a = parent1.parent_administration.order_by("?").first()
        mobile_a = MobileAssignment.objects.create_assignment(
            user=admin_user, name=f'mobile_a.{child_a.name.lower()}'
        )
        mobile_a.administrations.add(child_a)
        mobile_a.forms.add(form)

        child_b = parent2.parent_administration.order_by("?").first()
        mobile_b = MobileAssignment.objects.create_assignment(
            user=self.user, name=f'mobile_b.{child_b.name.lower()}'
        )
        mobile_b.administrations.add(child_b)
        mobile_b.forms.add(form)

        response = self.client.get(
            '/api/v1/mobile-assignments',
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {admin_token}'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json().get('data')
        self.assertTrue(
            len(data) == 1,
            "Admin should see assignments for their administration"
        )
        # Check that admin sees only assignments for their administration
        self.assertIn(
            child_a.id,
            [
                adm['id']
                for d in data
                for adm in d['administrations']
            ],
            "Admin should see only assignments for their administration"
        )
