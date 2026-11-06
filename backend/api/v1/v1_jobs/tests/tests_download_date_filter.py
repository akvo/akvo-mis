from datetime import timedelta
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.job import download_data
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from rest_framework import status


@override_settings(USE_TZ=False)
class DownloadDateFilterTestCase(TestCase, ProfileTestHelperMixin):
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
        call_command("default_roles_seeder", "--test", 1)
        self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.call_command("-r", 2, "--test", True)

        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()
        self.child_form_ids = list(
            self.form.children.values_list("id", flat=True)
        )
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

        # Set known dates on test data for predictable filtering
        now = timezone.now()
        self.today = now.date()
        self.yesterday = (now - timedelta(days=1)).date()
        self.three_days_ago = (now - timedelta(days=3)).date()
        self.five_days_ago = (now - timedelta(days=5)).date()

        # Get parent form data and set different created dates
        parents = list(
            self.form.form_form_data.filter(
                is_pending=False
            ).order_by("id").all()
        )
        self.assertTrue(
            len(parents) >= 2, "Need at least 2 parent records"
        )
        self.parent_old = parents[0]
        self.parent_recent = parents[1]

        # Set parent_old to 5 days ago, parent_recent to yesterday
        FormData.objects.filter(pk=self.parent_old.pk).update(
            created=timezone.now() - timedelta(days=5)
        )
        FormData.objects.filter(pk=self.parent_recent.pk).update(
            created=timezone.now() - timedelta(days=1)
        )

        # Set children dates
        old_children = list(
            self.parent_old.children.filter(
                is_pending=False
            ).all()
        )
        recent_children = list(
            self.parent_recent.children.filter(
                is_pending=False
            ).all()
        )

        # Old parent's children: set to yesterday (in range)
        for child in old_children:
            FormData.objects.filter(pk=child.pk).update(
                created=timezone.now() - timedelta(days=1)
            )

        # Recent parent's children: set to today
        for child in recent_children:
            FormData.objects.filter(pk=child.pk).update(
                created=timezone.now()
            )

        # Refresh from DB
        self.parent_old.refresh_from_db()
        self.parent_recent.refresh_from_db()

    def test_download_without_date_range_returns_all(self):
        """No date filter — existing behavior unchanged."""
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=self.child_form_ids,
        )
        parents = self.form.form_form_data.filter(
            is_pending=False
        )
        self.assertEqual(len(result), parents.count())

    def test_download_with_date_from_only(self):
        """Data before date_from excluded."""
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=[],
            date_from=str(self.yesterday),
        )
        for item in result:
            self.assertNotEqual(
                item["id"], self.parent_old.id,
                "Old parent should be excluded by date_from"
            )

    def test_download_with_date_to_only(self):
        """Data after date_to excluded."""
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=[],
            date_to=str(self.five_days_ago),
        )
        for item in result:
            self.assertNotEqual(
                item["id"], self.parent_recent.id,
                "Recent parent should be excluded by date_to"
            )

    def test_download_with_date_range(self):
        """Only data within range included."""
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=[],
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        result_ids = [item["id"] for item in result]
        self.assertIn(self.parent_recent.id, result_ids)
        self.assertNotIn(self.parent_old.id, result_ids)

    def test_download_date_boundary_inclusivity(self):
        """Data on date_from and date_to dates are included."""
        # Set parent to exactly yesterday
        FormData.objects.filter(pk=self.parent_recent.pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=[],
            date_from=str(self.yesterday),
            date_to=str(self.yesterday),
        )
        result_ids = [item["id"] for item in result]
        self.assertIn(
            self.parent_recent.id, result_ids,
            "Data on boundary date should be included"
        )

    def test_child_date_triggers_parent_inclusion(self):
        """Parent created outside range included via in-range children."""
        # parent_old created 5 days ago (outside range)
        # but its children were set to yesterday (in range)
        # Get actual child form IDs from existing children
        actual_child_form_ids = list(
            self.parent_old.children.filter(
                is_pending=False
            ).values_list("form_id", flat=True).distinct()
        )
        self.assertTrue(
            len(actual_child_form_ids) > 0,
            "parent_old must have children for this test"
        )
        # Verify children dates were set correctly
        children = self.parent_old.children.filter(
            is_pending=False
        )
        for child in children:
            child.refresh_from_db()
            self.assertTrue(
                child.created.date() >= self.three_days_ago,
                f"Child {child.id} created={child.created.date()} "
                f"should be >= {self.three_days_ago}"
            )
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=actual_child_form_ids,
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        # When children are merged, the child id overwrites parent id
        # in to_data_frame. Check by datapoint_name instead.
        result_names = [item["datapoint_name"] for item in result]
        self.assertIn(
            self.parent_old.name, result_names,
            "Parent should be included when its children "
            "are in date range"
        )

    def test_out_of_range_children_excluded(self):
        """Children created outside range not in output."""
        actual_child_form_ids = list(
            self.parent_old.children.filter(
                is_pending=False
            ).values_list("form_id", flat=True).distinct()
        )
        # Set old parent's children to 5 days ago (out of range)
        for child in self.parent_old.children.filter(
            is_pending=False
        ).all():
            FormData.objects.filter(pk=child.pk).update(
                created=timezone.now() - timedelta(days=5)
            )
        result = download_data(
            form=self.form,
            download_type=DataDownloadTypes.recent,
            child_form_ids=actual_child_form_ids,
            date_from=str(self.yesterday),
            date_to=str(self.today),
        )
        result_ids = [item["id"] for item in result]
        # parent_old should NOT be included now
        # (out of range itself, no in-range children)
        self.assertNotIn(
            self.parent_old.id, result_ids,
            "Parent with no in-range children and itself "
            "out of range should be excluded"
        )

    def test_download_with_date_range_and_administration(self):
        """Both date range and administration filters applied."""
        adm = self.parent_recent.administration
        result = download_data(
            form=self.form,
            administration_ids=[adm.id],
            download_type=DataDownloadTypes.recent,
            child_form_ids=[],
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        for item in result:
            self.assertIn(adm.name, item["administration"])


@override_settings(USE_TZ=False)
class DownloadDateFilterAPITestCase(TestCase, ProfileTestHelperMixin):
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
        call_command("default_roles_seeder", "--test", 1)
        self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.call_command("-r", 2, "--test", True)
        self.user = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()
        self.token = self.get_auth_token(
            email="admin@akvo.org", password="Test105*"
        )

    def test_invalid_date_range_returns_400(self):
        """date_from > date_to should return 400."""
        response = self.client.get(
            "/api/v1/download/generate",
            {
                "form_id": 1,
                "date_from": "2026-03-10",
                "date_to": "2026-03-01",
            },
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )
