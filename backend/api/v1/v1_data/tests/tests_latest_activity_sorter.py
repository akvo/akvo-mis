from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from api.v1.v1_forms.models import Forms
from api.v1.v1_data.functions import add_fake_answers
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class LatestActivitySortingTestCase(TestCase, ProfileTestHelperMixin):
    """Test cases for sorting form data by latest_activity."""

    def setUp(self):
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)

        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()
        self.administration = Administration.objects.filter(
            parent__isnull=False
        ).first()

        self.user = self.create_user(
            email="super@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        self.user.set_password("test")
        self.user.save()

        self.token = self.get_auth_token(self.user.email, "test")

        # Base time for creating test data
        self.base_time = timezone.now()

        # Create registration without monitoring (oldest activity)
        self.data_no_monitoring = self.form.form_form_data.create(
            name="No Monitoring Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        self.data_no_monitoring.created = self.base_time - timedelta(days=10)
        self.data_no_monitoring.updated = self.base_time - timedelta(days=10)
        self.data_no_monitoring.save()
        add_fake_answers(self.data_no_monitoring)

        # Create registration with old monitoring (middle activity)
        self.data_old_monitoring = self.form.form_form_data.create(
            name="Old Monitoring Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        self.data_old_monitoring.created = self.base_time - timedelta(days=8)
        self.data_old_monitoring.updated = self.base_time - timedelta(days=8)
        self.data_old_monitoring.save()
        add_fake_answers(self.data_old_monitoring)

        # Add monitoring child to data_old_monitoring
        self.old_monitoring_child = self.child_form.form_form_data.create(
            parent=self.data_old_monitoring,
            name="Old Monitoring Child",
            uuid=self.data_old_monitoring.uuid,
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        self.old_monitoring_child.created = self.base_time - timedelta(days=5)
        self.old_monitoring_child.updated = self.base_time - timedelta(days=5)
        self.old_monitoring_child.save()
        add_fake_answers(self.old_monitoring_child)

        # Create registration with recent monitoring (newest activity)
        self.data_recent_monitoring = self.form.form_form_data.create(
            name="Recent Monitoring Data",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        nine_days_ago = self.base_time - timedelta(days=9)
        self.data_recent_monitoring.created = nine_days_ago
        self.data_recent_monitoring.updated = nine_days_ago
        self.data_recent_monitoring.save()
        add_fake_answers(self.data_recent_monitoring)

        # Add monitoring child to data_recent_monitoring (most recent)
        self.recent_monitoring_child = self.child_form.form_form_data.create(
            parent=self.data_recent_monitoring,
            name="Recent Monitoring Child",
            uuid=self.data_recent_monitoring.uuid,
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        one_day_ago = self.base_time - timedelta(days=1)
        self.recent_monitoring_child.created = one_day_ago
        self.recent_monitoring_child.updated = one_day_ago
        self.recent_monitoring_child.save()
        add_fake_answers(self.recent_monitoring_child)

    def test_sort_by_latest_activity_descending(self):
        """Test sorting by latest_activity in descending order."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=latest_activity&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)

        ids = [item["id"] for item in data["data"]]

        # Expected order (most recent first):
        # 1. data_recent_monitoring (monitoring child updated 1 day ago)
        # 2. data_old_monitoring (monitoring child updated 5 days ago)
        # 3. data_no_monitoring (registration updated 10 days ago)
        self.assertEqual(ids[0], self.data_recent_monitoring.id)
        self.assertEqual(ids[1], self.data_old_monitoring.id)
        self.assertEqual(ids[2], self.data_no_monitoring.id)

    def test_sort_by_latest_activity_ascending(self):
        """Test sorting by latest_activity in ascending order."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=latest_activity&sort_type=ascend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)

        ids = [item["id"] for item in data["data"]]

        # Expected order (oldest first):
        # 1. data_no_monitoring (registration updated 10 days ago)
        # 2. data_old_monitoring (monitoring child updated 5 days ago)
        # 3. data_recent_monitoring (monitoring child updated 1 day ago)
        self.assertEqual(ids[0], self.data_no_monitoring.id)
        self.assertEqual(ids[1], self.data_old_monitoring.id)
        self.assertEqual(ids[2], self.data_recent_monitoring.id)

    def test_latest_activity_source_with_monitoring(self):
        """Test latest_activity_source shows form name for monitoring."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=latest_activity&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Find data_recent_monitoring in response
        recent_item = next(
            item for item in data["data"]
            if item["id"] == self.data_recent_monitoring.id
        )
        # Should have the monitoring form name as source
        self.assertEqual(
            recent_item["latest_activity_source"],
            self.child_form.name
        )

    def test_latest_activity_source_without_monitoring(self):
        """Test latest_activity_source is null for registration only."""
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=latest_activity&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Find data_no_monitoring in response
        no_monitoring_item = next(
            item for item in data["data"]
            if item["id"] == self.data_no_monitoring.id
        )
        # Should have null as source (no monitoring)
        self.assertIsNone(no_monitoring_item["latest_activity_source"])

    def test_latest_activity_uses_monitoring_over_registration(self):
        """Test that latest_activity uses monitoring date over registration."""
        response = self.client.get(
            f"/api/v1/form-data/{self.form.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Find data_old_monitoring in response
        old_monitoring_item = next(
            item for item in data["data"]
            if item["id"] == self.data_old_monitoring.id
        )

        # The latest_activity should be from monitoring (5 days ago)
        # not from registration (8 days ago)
        # We verify by checking it has a source (monitoring form name)
        self.assertEqual(
            old_monitoring_item["latest_activity_source"],
            self.child_form.name
        )

    def test_pending_monitoring_excluded_from_latest_activity(self):
        """Test that pending monitoring is excluded from latest_activity."""
        # Add a pending monitoring child (more recent than all others)
        pending_child = self.child_form.form_form_data.create(
            parent=self.data_no_monitoring,
            name="Pending Monitoring Child",
            uuid=self.data_no_monitoring.uuid,
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=True,  # Pending!
        )
        pending_child.updated = self.base_time  # Most recent
        pending_child.save()

        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                "?sort_by=latest_activity&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # data_no_monitoring should still be last (pending child excluded)
        ids = [item["id"] for item in data["data"]]
        self.assertEqual(ids[-1], self.data_no_monitoring.id)

        # And it should still have no source
        no_monitoring_item = next(
            item for item in data["data"]
            if item["id"] == self.data_no_monitoring.id
        )
        self.assertIsNone(no_monitoring_item["latest_activity_source"])

    def test_null_updated_child_uses_created_for_latest_activity(self):
        """Children with updated=NULL (flow-imported) must use created.

        latest_child_activity must fall back to children__created when
        children__updated is NULL, otherwise imported records are missed.
        """
        # Create a registration created long ago (simulates flow import)
        old_reg = self.form.form_form_data.create(
            name="OldFlowImport",
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        old_reg.created = self.base_time - timedelta(days=2000)
        old_reg.updated = None  # Simulates flow-imported record
        old_reg.save()

        # Monitoring child also has updated=NULL but created recently
        child_created = self.base_time - timedelta(days=1)
        child = self.child_form.form_form_data.create(
            parent=old_reg,
            name="FlowMonitoringChild",
            uuid=old_reg.uuid,
            administration=self.administration,
            geo=[0.0, 0.0],
            created_by=self.user,
            updated_by=self.user,
            is_pending=False,
        )
        child.created = child_created
        child.updated = None  # Simulates flow-imported record
        child.save()

        date_from = (self.base_time - timedelta(days=7)).date()
        date_to = self.base_time.date()

        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                f"?sort_by=latest_activity&sort_type=descend"
                f"&date_from={date_from}&date_to={date_to}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [item["id"] for item in data["data"]]

        # old_reg has a child created 1 day ago — must be included
        self.assertIn(old_reg.id, ids)

    def test_date_filter_uses_latest_activity_when_sorting_by_it(self):
        """Date filters should use latest_activity when
        sort_by=latest_activity.

        A registration created before date_from must appear if its most recent
        monitoring child falls within the requested date range.
        """
        # data_recent_monitoring was created 9 days ago (before date_from=8
        # days ago), but its child was updated 1 day ago (within range).
        date_from = (self.base_time - timedelta(days=7)).date()
        date_to = self.base_time.date()

        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                f"?sort_by=latest_activity&sort_type=descend"
                f"&date_from={date_from}&date_to={date_to}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [item["id"] for item in data["data"]]

        # data_recent_monitoring created 9 days ago but child updated 1 day
        # ago — must be included because its latest_activity is in range.
        self.assertIn(self.data_recent_monitoring.id, ids)

        # data_no_monitoring: created and updated 10 days ago — outside range.
        self.assertNotIn(self.data_no_monitoring.id, ids)

    def test_date_filter_uses_created_when_not_sorting_by_latest_activity(
        self,
    ):
        """Date filters should use created field when sort_by is not
        latest_activity, preserving existing behaviour."""
        self.data_recent_monitoring.refresh_from_db()
        created_date = self.data_recent_monitoring.created.date()

        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                f"?sort_by=created&sort_type=descend"
                f"&date_from={created_date}&date_to={created_date}"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [item["id"] for item in data["data"]]
        self.assertIn(self.data_recent_monitoring.id, ids)

    def test_latest_activity_fallback_for_parent_query(self):
        """Test latest_activity falls back to updated when parent provided."""
        # When querying with parent (monitoring data), latest_activity
        # should fallback to updated since monitoring records don't have
        # the latest_activity annotation
        response = self.client.get(
            (
                f"/api/v1/form-data/{self.form.id}"
                f"?parent={self.data_recent_monitoring.uuid}"
                "&sort_by=latest_activity&sort_type=descend"
            ),
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        # Should succeed (fallback to updated sorting)
        self.assertEqual(response.status_code, 200)
