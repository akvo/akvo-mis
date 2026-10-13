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
class MobileEntityValidationTestCase(TestCase, ProfileTestHelperMixin):

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command('form_seeder', '--test')
        call_command("entities_seeder", "--test", True)
        for entity in Entity.objects.all():
            for adm in Administration.objects.filter(
                parent__isnull=False
            ).all():
                EntityData.objects.create(
                    entity=entity,
                    administration=adm,
                    name=f"{entity.name} - {adm.name}"
                )
        # Superuser: this suite exercises entity validation, not the admin
        # scope rule MobileAssignmentSerializer enforces, and it assigns
        # administrations at every level. (Scope is covered by
        # MobileAssignmentAdminScopeTestCase.)
        self.user = self.create_user('test@akvo.org', self.IS_SUPER_ADMIN)
        self.token = self.get_auth_token(self.user.email)
        self.form = Forms.objects.get(pk=2)

    def test_entity_validation_in_middle_adm_level(self):
        adm = Administration.objects.filter(
            parent__isnull=False,
            level__level=1
        ).order_by('?').first()

        # remove entity data for the middle administration level
        adm.entity_data.all().delete()

        payload = {
            'name': 'secret',
            'forms': [self.form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                '/api/v1/mobile-assignments',
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {self.token}'
            )
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='secret')
        self.assertEqual(
            CustomPasscode().encode(data['passcode']),
            assignment.passcode
        )
        self.assertEqual(len(data['administrations']), 1)

    def test_entity_validation_in_multiple_middle_adm_levels(self):
        [adm1, adm2] = Administration.objects.filter(
            parent__isnull=False,
            level__level=1
        ).order_by('?').all()[:2]

        # remove entity data for the middle administration levels
        adm1.entity_data.all().delete()
        adm2.entity_data.all().delete()

        payload = {
            'name': 'double_secret',
            'forms': [self.form.id],
            'administrations': [adm1.id, adm2.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                '/api/v1/mobile-assignments',
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {self.token}'
            )
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='double_secret')
        self.assertEqual(
            CustomPasscode().encode(data['passcode']),
            assignment.passcode
        )
        self.assertEqual(len(data['administrations']), 2)

    def test_entity_validation_in_top_adm_level(self):
        adm = Administration.objects.filter(
            parent__isnull=True
        ).order_by('?').first()

        payload = {
            'name': 'top_secret',
            'forms': [self.form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                '/api/v1/mobile-assignments',
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {self.token}'
            )
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='top_secret')
        self.assertEqual(
            CustomPasscode().encode(data['passcode']),
            assignment.passcode
        )
        self.assertEqual(len(data['administrations']), 1)

    def test_entity_validation_in_bottom_adm_level(self):
        adm = Administration.objects.filter(
            parent__isnull=False,
            level__level=3
        ).order_by('?').first()

        # remove entity data for the bottom administration level
        adm.entity_data.all().delete()

        payload = {
            'name': 'bottom_secret',
            'forms': [self.form.id],
            'administrations': [adm.id],
        }

        response = typing.cast(
            HttpResponse,
            self.client.post(
                '/api/v1/mobile-assignments',
                payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {self.token}'
            )
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        assignment = MobileAssignment.objects.get(name='bottom_secret')
        self.assertEqual(
            CustomPasscode().encode(data['passcode']),
            assignment.passcode
        )
        self.assertEqual(len(data['administrations']), 1)
