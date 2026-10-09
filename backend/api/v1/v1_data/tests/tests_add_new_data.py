import re
import random
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class AddNewDataTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.form = Forms.objects.get(pk=1)

    def test_add_new_data_by_super_admin(self):
        adm = Administration.objects.filter(parent__isnull=True).first()
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        user = self.create_user(
            email="{0}.1@test.com".format(adm_name),
            role_level=self.IS_SUPER_ADMIN,
            administration=adm,
        )
        t = RefreshToken.for_user(user)
        token = t.access_token
        self.assertTrue(token)
        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")
        form_id = form.id
        adm = Administration.objects.filter(level__level=1).first()
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [{
                "question": 101,
                "value": "Jane"
            }, {
                "question": 102,
                "value": ["Male"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 2.0
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }, {
                "question": 107,
                "value": "photo.jpg"
            }, {
                "question": 108,
                "value": "2024-04-29"
            }, {
                "question": 109,
                "value": 0
            }, {
                "question": 114,
                "value": ["no"]
            }]
        }
        data = self.client.post('/api/v1/form-pending-data/{0}'
                                .format(form_id),
                                payload,
                                content_type='application/json',
                                **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # Super admin data should be saved directly without pending status
        form_data = FormData.objects.filter(
            form_id=form_id, is_pending=False
        ).first()
        self.assertEqual(form_data.name, "Testing Data")
        answers = Answers.objects.filter(data_id=form_data.id).count()
        self.assertGreater(answers, 0)
        # check administration answer value as integer
        data = self.client.get('/api/v1/data/{0}'
                               .format(form_data.id),
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        for d in data:
            if d.get('question') == 104:
                self.assertEqual(isinstance(d.get('value'), int), True)
            if d.get('question') == 109:
                self.assertEqual(d.get('value'), 0)

    def test_add_new_data_by_admin(self):
        adm = Administration.objects.filter(level__level=1).first()
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        email = ("{0}.{1}@test.com").format(
            adm_name,
            random.randint(1, 10)
        )
        # Create approver user
        self.create_user(
            email=f"{adm_name}.approver@test.com",
            role_level=self.IS_APPROVER,
            administration=adm,
            form=self.form,
        )
        # Create admin user
        user = self.create_user(
            email=email,
            role_level=self.IS_ADMIN,
            administration=adm,
            form=self.form,
        )
        # login
        auth_res = self.client.post(
            '/api/v1/login',
            {"email": user.email, "password": "password"},
            content_type='application/json'
        )
        token = auth_res.json().get("token")
        self.assertTrue(token)

        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")
        form_id = form.id
        payload = {
            "data": {
                "name": "Testing Data #2",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [{
                "question": 101,
                "value": "Jane"
            }, {
                "question": 102,
                "value": ["Male"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 2
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }, {
                "question": 107,
                "value": "photo.jpg"
            }, {
                "question": 108,
                "value": "2024-04-29"
            }, {
                "question": 109,
                "value": 2.5
            }, {
                "question": 114,
                "value": ["no"]
            }]
        }
        data = self.client.post(
            '/api/v1/form-pending-data/{0}'.format(form_id),
            payload,
            content_type='application/json',
            **{'HTTP_AUTHORIZATION': f'Bearer {token}'}
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # Check that data was created as pending
        pending_data = FormData.objects.filter(
            form_id=form_id, is_pending=True).first()
        self.assertEqual(pending_data.name, "Testing Data #2")
        form = Forms.objects.get(pk=2)
        national_adm = Administration.objects.filter(
            level__level=0
        ).first()
        self.create_user(
            email="supeer.approver@test.com",
            role_level=self.IS_APPROVER,
            administration=national_adm,
            form=form,
        )

        self.assertEqual(form.id, 2)
        self.assertEqual(form.name, "Test Form 2")
        form_id = form.id
        payload = {
            "data": {
                "name": "Testing Data National",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [{
                "question": 201,
                "value": "Jane"
            }, {
                "question": 202,
                "value": ["Male"]
            }, {
                "question": 203,
                "value": 31208200175
            }, {
                "question": 204,
                "value": 2
            }, {
                "question": 205,
                "value": [6.2088, 106.8456]
            }, {
                "question": 206,
                "value": ["Parent", "Children"]
            }]
        }
        data = self.client.post(
            '/api/v1/form-pending-data/{0}'.format(form_id),
            payload,
            content_type='application/json',
            **{'HTTP_AUTHORIZATION': f'Bearer {token}'}
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        form_data = FormData.objects.filter(
            name="Testing Data National",
            form_id=form_id
        ).first()
        self.assertEqual(form_data.name, "Testing Data National")
        answers = Answers.objects.filter(data=form_data).count()
        self.assertGreater(answers, 0)
        form_data = FormData.objects.filter(
            form_id=form_id, is_pending=False).count()
        self.assertEqual(form_data, 0)

    def test_add_new_data_by_data_entry(self):
        adm = Administration.objects.last()
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        email = ("{0}.{1}@test.com").format(
            adm_name,
            random.randint(1, 10)
        )
        # Create approver user
        self.create_user(
            email=f"{adm_name}.approver@test.com",
            role_level=self.IS_APPROVER,
            administration=adm,
            form=self.form,
        )
        # Create data entry user
        user = self.create_user(
            email=email,
            role_level=self.IS_ADMIN,
            administration=adm,
        )
        auth_res = self.client.post(
            '/api/v1/login',
            {"email": user.email, "password": "password"},
            content_type='application/json'
        )
        token = auth_res.json().get("token")
        self.assertTrue(token)

        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")
        form_id = form.id

        payload = {
            "data": {
                "name": "Testing Data Entry",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [{
                "question": 101,
                "value": "Jane"
            }, {
                "question": 102,
                "value": ["Male"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 2
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }, {
                "question": 107,
                "value": "photo.jpg"
            }, {
                "question": 108,
                "value": "2024-04-29"
            }, {
                "question": 114,
                "value": ["no"]
            }]
        }
        data = self.client.post('/api/v1/form-pending-data/{0}'
                                .format(form_id),
                                payload,
                                content_type='application/json',
                                **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # Regular form data should be zero
        # since this should create a pending entry
        form_data = FormData.objects.filter(
            form_id=form_id, is_pending=False
        ).count()
        self.assertEqual(form_data, 0)
        # Check pending form data
        pending_form_data = FormData.objects.filter(
            form_id=form_id, is_pending=True).first()
        self.assertEqual(pending_form_data.name, "Testing Data Entry")
        pending_answers = Answers.objects.filter(
            data_id=pending_form_data.id).count()
        self.assertGreater(pending_answers, 0)

    def test_add_new_data_by_data_entry_with_some_empty_values(self):
        adm = Administration.objects.filter(level__gt=1).order_by('?').first()
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        user = self.create_user(
            email="{}.emtpy@test.com".format(adm_name),
            role_level=self.IS_ADMIN,
            administration=adm,
        )
        # login
        auth_res = self.client.post(
            '/api/v1/login',
            {"email": user.email, "password": "password"},
            content_type='application/json'
        )
        token = auth_res.json().get("token")
        self.assertTrue(token)

        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")
        form_id = form.id
        payload = {
            "data": {
                "name": "Testing Data Entry",
                "administration": 2,
                "geo": [6.2088, 106.8456],
            },
            "answer": [{
                "question": 101,
                "value": ""
            }, {
                "question": 102,
                "value": []
            }, {
                "question": 103,
                "value": None
            }, {
                "question": 104,
                "value": 2
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }]
        }
        data = self.client.post('/api/v1/form-pending-data/{0}'
                                .format(form_id),
                                payload,
                                content_type='application/json',
                                **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 400)
        data = data.json()
        self.assertIn("101", data["message"])
        self.assertIn("102", data["message"])
        self.assertIn("value may not be null.", data["message"])
