"""
Tests for Flow Data Seeder parent-child relationship handling.

This module tests the registration and monitoring (parent-child) data
seeding functionality using call_command to test the actual end-to-end process.

Validates that:
1. Child FormData records correctly reference their parent via FormData.parent
2. Child data grouping by parent datapoint_id works properly
3. Administration IDs are inherited from parent to child
4. Geo values are inherited from parent when not provided in child data

Fixture data is located in: backend/api/v1/v1_data/tests/fixtures/

Note: This test file focuses on parent-child relationship functionality
that is NOT covered in other test files:
- tests_flow_data_seeder_funcs.py: AnswerProcessor, SeederConfig
- tests_flow_data_seeder_adm_mapping.py:
  load_administration_mappings, get_administration_id
- tests_flow_data_seeder_questions.py:
  load_questions, load_data_file, CsvColumns
- tests_flow_data_seeder_command.py: Command argument parsing, validation
"""

import os
import pandas as pd
import tempfile
import shutil
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings
from io import StringIO

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.models import Administration

from utils.seeder_config import SeederConfig


# =============================================================================
# Test Constants
# =============================================================================

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__),
    "fixtures"
)


# =============================================================================
# Base Test Class with Common Setup
# =============================================================================


@override_settings(USE_TZ=False, TEST_ENV=True)
class BaseFlowDataSeederTest(TestCase):
    """Base test class with common setup for flow data seeder tests."""

    def setUp(self):
        """Set up test environment with required data."""
        super().setUp()

        # Create administration data using seeder command
        call_command("administration_seeder", "--test")

        # Create forms (parent ID=4, child ID=40004) using form seeder
        call_command("form_seeder", "--test", 4)

        # The seeder creates registration (parent) FormData with EXPLICIT
        # ids equal to the fixture datapoint_ids (411-413) while monitoring
        # children auto-increment. PostgreSQL sequences are not rolled back
        # between TestCases, so under --parallel a prior test can leave the
        # 'data' sequence in the 411-413 range, making an auto-increment
        # child PK collide with an explicit parent PK. That IntegrityError
        # is swallowed inside an atomic block and poisons the transaction
        # (TransactionManagementError surfaces on the next query). Force the
        # sequence well above the explicit parent ids to remove the overlap.
        self._raise_form_data_sequence()

        # Create user
        self.user = SystemUser.objects.create_user(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="testpass123"
        )

        # Verify forms were created
        self.parent_form = Forms.objects.filter(id=4).first()
        self.child_form = Forms.objects.filter(id=40004).first()
        self.assertIsNotNone(
            self.parent_form, "Parent form (ID=4) should be created"
        )
        self.assertIsNotNone(
            self.child_form, "Child form (ID=40004) should be created"
        )

        # Get specific administrations for mapping based on fixture data
        # 411 and 412 use "Jakarta|East Jakarta|Kramat Jati"
        # 413 uses "Yogyakarta|Sleman|Seturan"
        self.admin_jakarta = Administration.objects.filter(
            name="Kramat Jati").first()
        self.admin_yogya = Administration.objects.filter(
            name="Seturan").first()
        self.assertIsNotNone(
            self.admin_jakarta, "Should have Kramat Jati administration"
        )
        self.assertIsNotNone(
            self.admin_yogya, "Should have Seturan administration"
        )

        # Create temporary source directory structure
        self.temp_source_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_source_dir, "data")
        os.makedirs(self.output_dir, exist_ok=True)

        # Copy and update fixture files
        self.copy_fixture_files()

    @staticmethod
    def _raise_form_data_sequence(floor=10_000_000):
        """Set the FormData PK sequence above the explicit parent PKs."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, false)",
                [FormData._meta.db_table, floor],
            )

    def copy_fixture_files(self):
        """Copy and update fixture files for testing."""
        # Read original fixture files
        parent_df = pd.read_csv(
            os.path.join(FIXTURES_DIR, "123_parent_data.csv")
        )
        child_df = pd.read_csv(
            os.path.join(FIXTURES_DIR, "123_child_data.csv")
        )
        admin_mapping_df = pd.read_csv(
            os.path.join(FIXTURES_DIR, "administration_mapping.csv")
        )

        # Update administration mapping to use actual administration IDs
        # Convert to string first to ensure consistent mapping
        admin_mapping_df["mis_value"] = admin_mapping_df["mis_value"]\
            .astype(str)
        admin_mapping_df["mis_value"] = admin_mapping_df["mis_value"].replace({
            "111": str(self.admin_jakarta.id),
            "222": str(self.admin_yogya.id),
        })

        # Write to temp directory
        parent_df.to_csv(
            os.path.join(self.output_dir, "123_parent_data.csv"),
            index=False
        )
        child_df.to_csv(
            os.path.join(self.output_dir, "123_child_data.csv"),
            index=False
        )
        admin_mapping_df.to_csv(
            os.path.join(self.temp_source_dir, "administration_mapping.csv"),
            index=False
        )

    def tearDown(self):
        """Clean up temporary directory."""
        super().tearDown()
        if os.path.exists(self.temp_source_dir):
            shutil.rmtree(self.temp_source_dir)

    def run_seeder_command(self, limit=None):
        """Helper method to run the seeder command with mocked source dir."""
        from unittest.mock import patch
        # Capture temp_source_dir for use in the closure
        temp_dir = self.temp_source_dir

        original_post_init = SeederConfig.__post_init__

        def custom_post_init(config_self):
            config_self.source_dir = temp_dir

        SeederConfig.__post_init__ = custom_post_init

        try:
            with patch(
                'api.v1.v1_data.management.commands'
                '.flow_data_seeder.get_form_by_flow_id'
            ) as mock_get_form, \
                 patch(
                'api.v1.v1_data.management.commands'
                '.flow_data_seeder.refresh_materialized_data'
            ):
                mock_get_form.return_value = self.parent_form
                out = StringIO()
                args = [
                    "flow_data_seeder",
                    "-f", "123",
                    "--email", "test@example.com"
                ]
                if limit:
                    args.extend(["--limit", str(limit)])
                call_command(*args, stdout=out, stderr=StringIO())
        finally:
            SeederConfig.__post_init__ = original_post_init


# =============================================================================
# Fixture Data Validation Tests
# =============================================================================


@override_settings(USE_TZ=False, TEST_ENV=True)
class FixtureDataValidationTestCase(TestCase):
    """Test suite for validating parent-child fixture data structure."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.fixture_dir = FIXTURES_DIR
        self.parent_csv = os.path.join(self.fixture_dir, "123_parent_data.csv")
        self.child_csv = os.path.join(self.fixture_dir, "123_child_data.csv")

    def test_parent_fixture_file_exists(self):
        """Test that parent fixture file exists."""
        self.assertTrue(
            os.path.exists(self.parent_csv),
            f"Parent fixture file not found: {self.parent_csv}"
        )

    def test_child_fixture_file_exists(self):
        """Test that child fixture file exists."""
        self.assertTrue(
            os.path.exists(self.child_csv),
            f"Child fixture file not found: {self.child_csv}"
        )

    def test_child_fixture_has_parent_column(self):
        """
        Test that child fixture CSV has the 'parent' column for relationships.
        """
        df = pd.read_csv(self.child_csv)
        self.assertIn(
            "parent",
            df.columns,
            "Child fixture must have 'parent' column "
            "for parent-child relationship"
        )

    def test_parent_fixture_has_expected_datapoints(self):
        """Test that parent fixture contains expected datapoint IDs."""
        df = pd.read_csv(self.parent_csv)
        datapoint_ids = df["datapoint_id"].tolist()
        self.assertIn(
            411, datapoint_ids, "Expected datapoint_id 411 in parent data"
        )
        self.assertIn(
            412, datapoint_ids, "Expected datapoint_id 412 in parent data"
        )

    def test_child_fixture_has_parent_references(self):
        """
        Test that child fixture contains parent
        references to parent datapoints.
        """
        df = pd.read_csv(self.child_csv)
        parent_ids = df["parent"].tolist()
        # From fixture: children have parent=411 and parent=413
        self.assertIn(411, parent_ids, "Expected child with parent=411")
        self.assertIn(413, parent_ids, "Expected child with parent=413")

    def test_child_fixture_multiple_children_for_parent_411(self):
        """Test that fixture has multiple children for parent datapoint 411."""
        df = pd.read_csv(self.child_csv)
        children_411 = df[df["parent"] == 411]
        self.assertEqual(
            len(children_411),
            2,
            "Expected 2 children for parent datapoint 411 in fixture"
        )


# =============================================================================
# Parent-Child Relationship Seeding Tests
# =============================================================================


class ParentChildRelationshipSeedingTestCase(BaseFlowDataSeederTest):
    """Test suite for parent-child relationship seeding using call_command."""

    def test_command_creates_parent_and_child_records(self):
        """Test that command creates both parent and child FormData records."""
        self.run_seeder_command()

        # Verify parent records were created
        parents = FormData.objects.filter(form=self.parent_form)
        self.assertEqual(
            parents.count(),
            3,
            "Should have created 3 parent FormData records"
        )

        # Verify child records were created
        children = FormData.objects.filter(form=self.child_form)
        self.assertEqual(
            children.count(),
            3,
            "Should have created 3 child FormData records"
        )

    def test_child_records_reference_parent_correctly(self):
        """Test that child FormData have correct parent reference."""
        self.run_seeder_command()

        # Get parent with uuid matching fixture (datapoint 411)
        parent_411 = FormData.objects.filter(
            form=self.parent_form,
            uuid="124-abd01-4"
        ).first()
        self.assertIsNotNone(parent_411, "Parent 411 should be created")

        # Verify children with parent=411 reference correct parent
        children_of_411 = FormData.objects.filter(
            form=self.child_form,
            parent=parent_411
        )
        # From fixture: 2 children (5001, 5002) have parent=411
        self.assertEqual(
            children_of_411.count(),
            2,
            "Parent 411 should have 2 children"
        )

        # Verify each child has correct parent_id
        for child in children_of_411:
            self.assertEqual(
                child.parent_id,
                parent_411.pk,
                f"Child {child.id} should have parent_id = {parent_411.pk}"
            )

    def test_parent_records_have_no_parent_reference(self):
        """Test that parent FormData records have no parent reference."""
        self.run_seeder_command()

        # All parent records should have parent=None
        parents = FormData.objects.filter(form=self.parent_form)
        for parent in parents:
            self.assertIsNone(
                parent.parent,
                f"Parent FormData {parent.id} should have no parent"
            )

    def test_multiple_children_per_parent_via_reverse_relation(self):
        """
        Test that parent FormData can access multiple
        children via reverse relation.
        """
        self.run_seeder_command()

        # Get parent 411
        parent_411 = FormData.objects.filter(
            form=self.parent_form,
            uuid="124-abd01-4"
        ).first()

        # Use reverse relationship to count children
        children_count = parent_411.children.count()
        self.assertEqual(
            children_count,
            2,
            "Parent 411 should have 2 children via reverse relation"
        )

    def test_geo_values_from_csv_are_stored(self):
        """Test that geo values from CSV are correctly stored."""
        self.run_seeder_command()

        # Parent 411 has geo="101.0|0.0"
        parent_411 = FormData.objects.filter(
            form=self.parent_form,
            uuid="124-abd01-4"
        ).first()
        self.assertIsNotNone(parent_411)
        self.assertEqual(parent_411.geo, [101.0, 0.0])

        # Parent 412 has geo="101.0|1.0"
        parent_412 = FormData.objects.filter(
            form=self.parent_form,
            uuid="124-abd01-5"
        ).first()
        self.assertIsNotNone(parent_412)
        self.assertEqual(parent_412.geo, [101.0, 1.0])

    def test_child_form_has_parent_relationship_set(self):
        """Test that child form has parent_form set correctly."""
        # Verify child form has parent set
        self.assertEqual(
            self.child_form.parent_id,
            self.parent_form.id,
            "Child form should have parent_form set to parent form"
        )


# =============================================================================
# Limit Tests with Parent-Child Relationships
# =============================================================================


class LimitWithParentChildRelationshipsTestCase(BaseFlowDataSeederTest):
    """Test suite for limit functionality with parent-child relationships."""

    def test_limit_filters_both_parent_and_child_correctly(self):
        """
        Test that limit filters parents and
        only includes children for limited parents.
        """
        self.run_seeder_command(limit=2)

        # Should have 2 parent records
        parents = FormData.objects.filter(form=self.parent_form)
        self.assertEqual(
            parents.count(), 2, "Limit should create 2 parent records"
        )

        # Should have children only for the 2 limited parents
        # From fixture:
        # Parent 411 has 2 children (411, 412), Parent 412 has 0 children
        # Total: 2 children
        children = FormData.objects.filter(form=self.child_form)
        self.assertEqual(
            children.count(),
            2,
            "Should only have children for the 2 limited parents"
        )


# =============================================================================
# Revert Tests with Parent-Child Relationships
# =============================================================================


class RevertParentChildRelationshipsTestCase(BaseFlowDataSeederTest):
    """Test suite for revert functionality with parent-child relationships."""

    def test_revert_removes_both_parent_and_child_records(self):
        """Test that revert removes both parent and child FormData records."""
        from unittest.mock import patch
        # First, seed the data
        self.run_seeder_command()

        # Verify records were created
        parent_count_before = FormData.objects.filter(
            form=self.parent_form).count()
        child_count_before = FormData.objects.filter(
            form=self.child_form).count()
        self.assertGreater(parent_count_before, 0)
        self.assertGreater(child_count_before, 0)

        # Now revert
        temp_dir = self.temp_source_dir
        original_post_init = SeederConfig.__post_init__

        def custom_post_init(config_self):
            config_self.source_dir = temp_dir

        SeederConfig.__post_init__ = custom_post_init

        try:
            with patch(
                'api.v1.v1_data.management.commands'
                '.flow_data_seeder.get_form_by_flow_id'
            ) as mock_get_form, \
                 patch(
                'api.v1.v1_data.management.commands'
                '.flow_data_seeder.refresh_materialized_data'
            ):
                mock_get_form.return_value = self.parent_form
                out = StringIO()
                call_command(
                    "flow_data_seeder",
                    "-f", "123",
                    "--revert",
                    stdout=out,
                    stderr=StringIO()
                )
        finally:
            SeederConfig.__post_init__ = original_post_init

        # Verify records were removed
        parent_count_after = FormData.objects.filter(
            form=self.parent_form).count()
        child_count_after = FormData.objects.filter(
            form=self.child_form).count()

        self.assertEqual(
            parent_count_after, 0, "All parent records should be removed"
        )
        self.assertEqual(
            child_count_after, 0, "All child records should be removed"
        )


# =============================================================================
# Administration Inheritance Tests
# =============================================================================


class AdministrationInheritanceTestCase(BaseFlowDataSeederTest):
    """Test suite for administration ID inheritance from parent to child."""

    def test_child_inherits_administration_from_parent(self):
        """Test that child records inherit administration_id from parent."""
        self.run_seeder_command()

        # Get parent and child records
        parent = FormData.objects.filter(
            form=self.parent_form,
            uuid="124-abd01-4"
        ).first()
        self.assertIsNotNone(parent)

        children = FormData.objects.filter(
            form=self.child_form,
            parent=parent
        )

        # All children should have the same administration_id as parent
        for child in children:
            self.assertEqual(
                child.administration_id,
                parent.administration_id,
                "Child should inherit parent's administration_id"
            )
