import pandas as pd
import os
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from api.v1.v1_forms.models import Questions, Forms
from api.v1.v1_jobs.job import download_data, generate_definition_sheet
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from utils.export_form import blank_data_template
from utils.custom_helper import CustomPasscode


@override_settings(USE_TZ=False)
class BulkUnitTestCase(TestCase, ProfileTestHelperMixin):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("form_seeder", "--test")
        rows = [
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-JK",
                "Province_1": "Jakarta",
                "code_2": "ID-JK-JKE",
                "District_2": "East Jakarta",
                "code_3": "ID-JK-JKE-KJ",
                "Subdistrict_3": "Kramat Jati",
                "code_4": "ID-JK-JKE-KJ-CW",
                "Village_4": "Cawang",
            },
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-JK",
                "Province_1": "Jakarta",
                "code_2": "ID-JK-JKW",
                "District_2": "West Jakarta",
                "code_3": "ID-JK-JKW-KJ",
                "Subdistrict_3": "Kebon Jeruk",
                "code_4": "ID-JK-JKW-KJ-KJ",
                "Village_4": "Kebon Jeruk",
            },
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-YO",
                "Province_1": "Yogyakarta",
                "code_2": "ID-YO-SL",
                "District_2": "Sleman",
                "code_3": "ID-YO-SL-ST",
                "Subdistrict_3": "Seturan",
                "code_4": "ID-YO-SL-ST-CB",
                "Village_4": "Cepit Baru",
            },
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-YO",
                "Province_1": "Yogyakarta",
                "code_2": "ID-YO-BT",
                "District_2": "Bantul",
                "code_3": "ID-YO-BT-BT",
                "Subdistrict_3": "Bantul",
                "code_4": "ID-YO-BT-BT-BT",
                "Village_4": "Bantul",
            },
        ]
        administration_seeder.seed_administration_test(rows=rows)
        # Seed default roles after administration seeder
        call_command("default_roles_seeder", "--test", 1)

        self.client.post(
            '/api/v1/login',
            {
                "email": "admin@akvo.org",
                "password": "Test105*"
            },
            content_type='application/json'
        )
        self.call_command("-r", 2, "--test", True)

        # Create a mobile assignment for the user
        user = SystemUser.objects.filter(email="admin@akvo.org").first()
        mobile_user = user.mobile_assignments.create(
            name="Test mobile",
            passcode=CustomPasscode().encode("123456"),
        )
        # Assign administration to the mobile assignment
        user_adm = Administration.objects.filter(parent__isnull=True).first()
        mobile_user.administrations.add(
            user_adm
        )
        self.form = Forms.objects.get(pk=4)
        # Assign form to the mobile assignment
        mobile_user.forms.add(self.form)

        self.mobile_user = mobile_user
        self.code = CustomPasscode().decode(
            encoded_passcode=self.mobile_user.passcode
        )
        res = self.client.post(
            "/api/v1/device/auth",
            {"code": self.code},
            content_type="application/json",
        )
        data = res.json()
        self.token = data["syncToken"]

    def seed_repeatable_form_data(self):
        form = Forms.objects.get(pk=4)
        adm = self.mobile_user.administrations.first()
        payload = {
            "formId": form.id,
            "name": "Repeatable Test",
            "duration": 1,
            "submittedAt": "2025-09-02T02:38:13.807Z",
            "submitter": self.mobile_user.name,
            "geo": [6.2088, 106.8456],
            "answers": {
                442: "Jane Doe",
                443: "/attachment/screenshot_likes_123.jpeg",
                444: "/attachments/my_works_123.pdf",
                445: "/attachment/application_letter_2025-09-01.pdf",
                446: adm.id if adm else 1,
                551: "data:base64,examplesignature123",
                661: "Good Job!",
                "661-1": "Awesome work!",
                "661-2": "Lovely!",
            },
        }
        response = self.client.post(
            "/api/v1/device/sync",
            payload,
            follow=True,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_data_download_with_download_type_all(self):
        form = Forms.objects.get(pk=1)
        child_forms = form.children.filter(pk=10001)
        download_response = download_data(
            form=form,
            download_type=DataDownloadTypes.all,
            child_form_ids=list(child_forms.values_list("id", flat=True))
        )
        # 2 registrations with 2 monitoring data each
        self.assertEqual(len(download_response), 4)

    def test_data_download_with_download_type_all_no_children(self):
        form = Forms.objects.get(pk=1)
        for d in form.form_form_data.all():
            for child in d.children.all():
                # Mark all children as pending
                # to simulate no completed children
                child.is_pending = True
                child.save()
        download_response = download_data(
            form=form,
            download_type=DataDownloadTypes.all,
            child_form_ids=[]
        )
        # 2 registrations with no children
        self.assertEqual(len(download_response), 2)

    def test_data_download_with_download_type_recent(self):
        form = Forms.objects.get(pk=1)
        child_forms = form.children.filter(pk=10001)
        download_response = download_data(
            form=form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=list(child_forms.values_list("id", flat=True))
        )
        # 2 registration with the latest data
        self.assertEqual(len(download_response), 2)

    def test_data_download_repeatable_questions(self):
        # Remove existing form data to avoid interference
        self.form.form_form_data.all().delete(hard=True)
        self.seed_repeatable_form_data()
        form_data = self.form.form_form_data.order_by("?").first()
        administration = form_data.administration
        download_response = download_data(
            form=self.form,
            administration_ids=[administration.id],
        )
        self.assertTrue(download_response)
        download_columns = list(download_response[0].keys())
        questions = Questions.objects.filter(form=form_data.form).values_list(
            "name", flat=True)
        meta_columns = [
            "id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "datapoint_name",
            "administration",
            "geolocation"
        ]
        columns = list(
            filter(lambda x: x not in meta_columns, download_columns)
        )
        self.assertEqual(list(columns).sort(), list(questions).sort())

        self.assertCountEqual(
            columns,
            [
                'uuid',
                'name',
                'upload_screenshot_proof',
                'upload_work',
                'letter_of_application',
                'subdistrict',
                'signature',
                'testimonial_1',
                'testimonial_2',
                'testimonial_3'
            ]
        )

    def test_data_download_list_of_columns(self):
        form = Forms.objects.get(pk=1)
        child_forms = form.children.filter(pk=10002)
        self.assertTrue(form)
        form_data = form.form_form_data.order_by("?").first()
        administration = form_data.administration
        download_response = download_data(
            form=form,
            administration_ids=[administration.id],
            child_form_ids=list(child_forms.values_list("id", flat=True))
        )
        self.assertTrue(download_response)
        download_columns = list(download_response[0].keys())
        questions = Questions.objects.filter(form=form_data.form).values_list(
            "name", flat=True)
        meta_columns = [
            "id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "datapoint_name",
            "administration",
            "geolocation"
        ]
        columns = list(
            filter(lambda x: x not in meta_columns, download_columns)
        )
        self.assertEqual(list(columns).sort(), list(questions).sort())

        self.assertCountEqual(
            columns,
            [
                'uuid',
                'name',
                'gender',
                'phone',
                'location',
                'example_geolocation',
                'family_members',
                'picture',
                'data',
                'decimal',
                'multiple_of_two',
                'do_you_have_pets',
                'whats_the_pet',
                'monitoring_date',
            ]
        )

    def test_generate_definition_sheet(self):
        form = Forms.objects.first()
        writer = pd.ExcelWriter("test.xlsx", engine='xlsxwriter')
        generate_definition_sheet(
            writer=writer,
            form=form
        )
        writer.save()
        # test if excel has been created
        self.assertTrue(os.path.exists("test.xlsx"))
        os.remove("test.xlsx")

    def test_generate_definition_sheet_with_child_forms(self):
        form = Forms.objects.get(pk=1)
        child_forms = form.children.filter(pk=10002)
        writer = pd.ExcelWriter("test.xlsx", engine='xlsxwriter')
        generate_definition_sheet(
            writer=writer,
            form=form,
            child_form_ids=list(child_forms.values_list("id", flat=True)),
        )
        writer.save()
        # test if excel has been created
        self.assertTrue(os.path.exists("test.xlsx"))
        os.remove("test.xlsx")

    def test_blank_data_template(self):
        form = Forms.objects.first()
        writer = pd.ExcelWriter("test.xlsx", engine='xlsxwriter')
        blank_data_template(
            writer=writer,
            form=form
        )
        writer.save()
        # test if excel has been created
        self.assertTrue(os.path.exists("test.xlsx"))
        os.remove("test.xlsx")
