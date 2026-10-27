from datetime import timedelta
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_jobs.job import download_monitoring_data
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False)
class DownloadMonitoringDataTestCase(TestCase, ProfileTestHelperMixin):
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

        now = timezone.now()
        self.today = now.date()
        self.yesterday = (now - timedelta(days=1)).date()
        self.three_days_ago = (now - timedelta(days=3)).date()
        self.five_days_ago = (now - timedelta(days=5)).date()

    def test_returns_child_ids_not_parent_ids(self):
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
        )
        self.assertTrue(len(result) > 0)
        parent_ids = set(
            self.form.form_form_data.filter(
                is_pending=False
            ).values_list("id", flat=True)
        )
        for row in result:
            self.assertIn("parent_id", row)
            self.assertIn(row["parent_id"], parent_ids)
            # id should be the monitoring record's own id
            self.assertNotEqual(row["id"], row["parent_id"])

    def test_recent_one_per_parent(self):
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            download_type=DataDownloadTypes.recent,
        )
        parent_ids = [row["parent_id"] for row in result]
        self.assertEqual(len(parent_ids), len(set(parent_ids)))

    def test_all_multiple_per_parent(self):
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            download_type=DataDownloadTypes.all,
        )
        parent_ids = [row["parent_id"] for row in result]
        unique_parents = set(parent_ids)
        self.assertGreaterEqual(len(result), len(unique_parents))

    def test_with_administration_filter(self):
        parents = list(
            self.form.form_form_data.filter(
                is_pending=False
            ).all()
        )
        adm = parents[0].administration
        adm_ids = [adm.id]
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            administration_ids=adm_ids,
        )
        for row in result:
            parent = FormData.objects.get(pk=row["parent_id"])
            self.assertEqual(parent.administration_id, adm.id)

    def test_with_date_from(self):
        # Set monitoring records: some old, some recent
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        self.assertTrue(len(children) >= 2)
        # Make first child old
        FormData.objects.filter(pk=children[0].pk).update(
            created=timezone.now() - timedelta(days=5)
        )
        # Make second child recent
        FormData.objects.filter(pk=children[1].pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_from=str(self.three_days_ago),
        )
        result_ids = [row["id"] for row in result]
        self.assertNotIn(children[0].id, result_ids)
        self.assertIn(children[1].id, result_ids)

    def test_with_date_to(self):
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        self.assertTrue(len(children) >= 2)
        FormData.objects.filter(pk=children[0].pk).update(
            created=timezone.now() - timedelta(days=5)
        )
        FormData.objects.filter(pk=children[1].pk).update(
            created=timezone.now()
        )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_to=str(self.three_days_ago),
        )
        result_ids = [row["id"] for row in result]
        self.assertIn(children[0].id, result_ids)
        self.assertNotIn(children[1].id, result_ids)

    def test_with_date_range(self):
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        self.assertTrue(len(children) >= 2)
        FormData.objects.filter(pk=children[0].pk).update(
            created=timezone.now() - timedelta(days=5)
        )
        FormData.objects.filter(pk=children[1].pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        result_ids = [row["id"] for row in result]
        self.assertNotIn(children[0].id, result_ids)
        self.assertIn(children[1].id, result_ids)

    def test_date_boundary_inclusivity(self):
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        self.assertTrue(len(children) >= 1)
        FormData.objects.filter(pk=children[0].pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_from=str(self.yesterday),
            date_to=str(self.yesterday),
        )
        result_ids = [row["id"] for row in result]
        self.assertIn(children[0].id, result_ids)

    def test_empty_result_with_out_of_range_dates(self):
        far_future = str(
            (timezone.now() + timedelta(days=365)).date()
        )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_from=far_future,
        )
        self.assertEqual(len(result), 0)

    def test_with_date_and_administration(self):
        parents = list(
            self.form.form_form_data.filter(
                is_pending=False
            ).all()
        )
        adm = parents[0].administration
        children = list(
            FormData.objects.filter(
                form=self.child_form,
                parent=parents[0],
                is_pending=False,
            ).all()
        )
        if children:
            FormData.objects.filter(pk=children[0].pk).update(
                created=timezone.now() - timedelta(days=1)
            )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            administration_ids=[adm.id],
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        for row in result:
            parent = FormData.objects.get(pk=row["parent_id"])
            self.assertEqual(parent.administration_id, adm.id)

    def test_monitoring_date_filter_independent_from_parent(self):
        """Parent created outside range, monitoring in range."""
        parents = list(
            self.form.form_form_data.filter(
                is_pending=False
            ).order_by("id").all()
        )
        parent = parents[0]
        # Parent: 5 days ago (outside range)
        FormData.objects.filter(pk=parent.pk).update(
            created=timezone.now() - timedelta(days=5)
        )
        # Child: yesterday (in range)
        children = list(
            parent.children.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        if children:
            FormData.objects.filter(pk=children[0].pk).update(
                created=timezone.now() - timedelta(days=1)
            )
            result = download_monitoring_data(
                parent_form=self.form,
                child_form=self.child_form,
                date_from=str(self.three_days_ago),
                date_to=str(self.today),
            )
            result_ids = [row["id"] for row in result]
            self.assertIn(children[0].id, result_ids)
            matching = [r for r in result if r["id"] == children[0].id]
            self.assertEqual(matching[0]["parent_id"], parent.id)

    def test_monitoring_excludes_out_of_range_even_if_parent_in_range(self):
        """Parent in range, monitoring out of range."""
        parents = list(
            self.form.form_form_data.filter(
                is_pending=False
            ).order_by("id").all()
        )
        parent = parents[0]
        # Parent: yesterday (in range)
        FormData.objects.filter(pk=parent.pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        # Child: 5 days ago (out of range)
        children = list(
            parent.children.filter(
                form=self.child_form,
                is_pending=False,
            ).all()
        )
        for child in children:
            FormData.objects.filter(pk=child.pk).update(
                created=timezone.now() - timedelta(days=5)
            )
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
            date_from=str(self.three_days_ago),
            date_to=str(self.today),
        )
        result_ids = [row["id"] for row in result]
        for child in children:
            self.assertNotIn(child.id, result_ids)

    def test_datapoint_name_from_parent(self):
        result = download_monitoring_data(
            parent_form=self.form,
            child_form=self.child_form,
        )
        for row in result:
            parent = FormData.objects.get(pk=row["parent_id"])
            self.assertEqual(row["datapoint_name"], parent.name)
