from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_visualization.constants import (
    DashboardStatus,
    DashboardVisibility,
)
from api.v1.v1_visualization.models import Dashboard


@override_settings(USE_TZ=False, TEST_ENV=True)
class DashboardVisibilityTestCase(TestCase):
    """Visibility is independent of publication (VIZ-010 D-5)."""

    def setUp(self):
        self.form = Forms.objects.create(
            name="Registration", type=FormTypes.registration, version=1
        )

    def test_a_new_dashboard_is_internal(self):
        """Every dashboard that exists today is internal, and stays so.

        The migration adds the column with this default and backfills
        nothing, because internal is what every existing row already was.
        """
        dashboard = Dashboard.objects.create(
            name="Water points", slug="water-points", root_form=self.form
        )
        self.assertEqual(
            dashboard.visibility, DashboardVisibility.internal
        )

    def test_visibility_and_status_are_independent(self):
        # A public draft: nobody can read it, because the public read path
        # requires published as well.
        draft = Dashboard.objects.create(
            name="Draft",
            slug="draft",
            root_form=self.form,
            visibility=DashboardVisibility.public,
        )
        self.assertEqual(draft.status, DashboardStatus.draft)
        self.assertEqual(draft.visibility, DashboardVisibility.public)

        # An internal published dashboard: readable, but only with a login.
        internal = Dashboard.objects.create(
            name="Internal",
            slug="internal",
            root_form=self.form,
            status=DashboardStatus.published,
        )
        self.assertEqual(
            internal.visibility, DashboardVisibility.internal
        )

    def test_the_vocabulary_reads_back(self):
        self.assertEqual(
            DashboardVisibility.FieldStr[DashboardVisibility.internal],
            "internal",
        )
        self.assertEqual(
            DashboardVisibility.FieldStr[DashboardVisibility.public],
            "public",
        )


class DashboardSharePublicAccessTestCase(TestCase):
    """Sharing publicly is its own permission (VIZ-010 D-6)."""

    def test_it_continues_the_dashboard_block(self):
        # VIZ-002 took 8-12; this is the next value, not a reused gap.
        self.assertEqual(FeatureAccessTypes.dashboard_share_public, 13)

    def test_it_is_grouped_with_the_dashboard_builder_feature(self):
        group = FeatureTypes.FieldGroup[FeatureTypes.dashboard_builder]
        self.assertIn(FeatureAccessTypes.dashboard_share_public, group)

    def test_it_is_distinct_from_publishing(self):
        """Publishing to colleagues and to the internet differ.

        A role that may do the first must not automatically do the second,
        which is only true while these are two access types.
        """
        self.assertNotEqual(
            FeatureAccessTypes.dashboard_publish,
            FeatureAccessTypes.dashboard_share_public,
        )

    def test_it_has_a_label_the_role_editor_can_render(self):
        self.assertEqual(
            FeatureAccessTypes.FieldStr[
                FeatureAccessTypes.dashboard_share_public
            ],
            "Dashboard Share Publicly",
        )
