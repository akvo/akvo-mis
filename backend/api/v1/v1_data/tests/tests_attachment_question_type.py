import re
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class AddNewDataTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.form = Forms.objects.get(pk=4)
        adm = (
            Administration.objects
            .filter(parent__isnull=False)
            .order_by("?").first()
        )
        adm_name = re.sub("[^A-Za-z0-9]+", "", adm.name.lower())
        user = self.create_user(
            email="{0}.123@test.com".format(adm_name),
            role_level=self.IS_SUPER_ADMIN,
            administration=adm,
        )
        t = RefreshToken.for_user(user)
        token = t.access_token
        self.adm = adm
        self.headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_new_submission_created_successfully(self):
        form_id = self.form.id
        payload = {
            "data": {
                "name": "Testing Attachment",
                "administration": self.adm.id,
                "geo": [7.2088, 126.8456],
            },
            "answer": [{
                "question": 442,
                "value": "John Doe"
            }, {
                "question": 443,
                "value": "/images/screenshoot_2023-10-02_11-23-45.png"
            }, {
                "question": 444,
                "value": "/attachments/my_work.pdf"
            }, {
                "question": 445,
                "value": "/attachments/application.pdf"
            }, {
                "question": 446,
                "value": self.adm.id
            }, {
                "question": 551,
                "value": "data:base64,signature123"
            }]
        }
        data = self.client.post(
            f'/api/v1/form-pending-data/{form_id}',
            payload,
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
