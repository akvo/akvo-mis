from django.test.utils import override_settings
from rest_framework.test import APITestCase

from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import (
    Administration,
    Role,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_users.models import SystemUser
from api.v1.v1_forms.constants import FormTypes
from api.v1.v1_forms.models import Forms
from api.v1.v1_visualization.constants import DashboardVisibility
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.tests.mixins import (
    VisualizationValuesTestMixin,
)

MANAGE = "/api/v1/manage/dashboards"


@override_settings(USE_TZ=False, TEST_ENV=True)
class DashboardVisibilityApiTestCase(
    VisualizationValuesTestMixin, APITestCase
):
    """Who may make a dashboard public (VIZ-010 D-6).

    Publishing to colleagues and publishing to the internet are different
    acts. `dashboard_edit` carries the first; only `dashboard_share_public`
    carries the second, and the check is on the field rather than on the
    action because both arrive in the same PUT.
    """

    def setUp(self):
        super().setUp()
        self.dashboard = Dashboard.objects.create(
            name="Water points",
            slug="water-points",
            root_form=self.registration,
        )

    def payload(self, **overrides):
        body = {
            "name": "Water points",
            "description": None,
            "default_filters": {},
            "widgets": [],
        }
        body.update(overrides)
        return body

    def put(self, **overrides):
        return self.client.put(
            f"{MANAGE}/{self.dashboard.id}",
            self.payload(**overrides),
            format="json",
        )

    def editor_without_sharing(self):
        """A role holding every dashboard access except sharing."""
        administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        role = Role.objects.create(
            name="Editor",
            administration_level=administration.level,
        )
        for access in (
            FeatureAccessTypes.dashboard_view,
            FeatureAccessTypes.dashboard_create,
            FeatureAccessTypes.dashboard_edit,
            FeatureAccessTypes.dashboard_publish,
            FeatureAccessTypes.dashboard_delete,
        ):
            RoleFeatureAccess.objects.create(
                role=role,
                type=FeatureTypes.dashboard_builder,
                access=access,
            )
        editor = SystemUser.objects.create_user(
            email="editor@akvo.org",
            password="Secret#Pass123",
            first_name="Ed",
            last_name="Itor",
        )
        UserRole.objects.create(
            user=editor, role=role, administration=administration
        )
        return editor

    # ── reading ──────────────────────────────────────────────────────

    def test_visibility_is_served_as_a_string(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{MANAGE}/{self.dashboard.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visibility"], "internal")

    def test_it_appears_in_the_list_too(self):
        self.client.force_authenticate(user=self.user)
        rows = self.client.get(MANAGE).json()
        self.assertEqual(rows[0]["visibility"], "internal")

    # ── writing ──────────────────────────────────────────────────────

    def test_a_sharer_can_make_it_public(self):
        self.client.force_authenticate(user=self.user)
        response = self.put(visibility="public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visibility"], "public")
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.public
        )

    def test_a_sharer_can_take_it_back(self):
        self.dashboard.visibility = DashboardVisibility.public
        self.dashboard.save()
        self.client.force_authenticate(user=self.user)

        response = self.put(visibility="internal")
        self.assertEqual(response.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.internal
        )

    def test_an_editor_without_the_access_is_refused(self):
        self.client.force_authenticate(user=self.editor_without_sharing())
        response = self.put(visibility="public")
        self.assertEqual(response.status_code, 403)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.internal
        )

    def test_that_editor_can_still_save_everything_else(self):
        """The gate is the field, not the action.

        An editor who cannot share must still be able to save a
        dashboard, including one that is already public.
        """
        self.dashboard.visibility = DashboardVisibility.public
        self.dashboard.save()
        self.client.force_authenticate(user=self.editor_without_sharing())

        # Same value, so nothing is being changed.
        response = self.put(name="Renamed", visibility="public")
        self.assertEqual(response.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.name, "Renamed")
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.public
        )

    def test_omitting_it_leaves_it_alone(self):
        self.dashboard.visibility = DashboardVisibility.public
        self.dashboard.save()
        self.client.force_authenticate(user=self.user)

        response = self.put(name="Renamed")
        self.assertEqual(response.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.public
        )

    def test_an_unknown_value_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.put(visibility="everyone")
        self.assertEqual(response.status_code, 400)
        self.dashboard.refresh_from_db()
        self.assertEqual(
            self.dashboard.visibility, DashboardVisibility.internal
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class PreviewWidgetTestCase(VisualizationValuesTestMixin, APITestCase):
    """Data for a widget the author has not saved yet (VIZ-010).

    The canvas renders unsaved state, so its widgets carry temporary
    negative ids. `validate_dashboard_payload` checks that a widget id
    belongs to the dashboard — right for the wholesale replace on PUT, and
    wrong here, where the id belongs to nothing by definition. It rejected
    every preview, which meant every widget on the canvas failed to load.
    """

    def setUp(self):
        super().setUp()
        self.dashboard = Dashboard.objects.create(
            name="Water points",
            slug="water-points",
            root_form=self.registration,
        )
        self.client.force_authenticate(user=self.user)

    def preview(self, widget, filters=None):
        return self.client.post(
            f"{MANAGE}/{self.dashboard.id}/preview-widget",
            {"widget": widget, "filters": filters or {}},
            format="json",
        )

    def test_a_widget_with_a_temporary_id_is_previewed(self):
        response = self.preview(
            {
                "id": -1,
                "type": "bar",
                "col_span": 12,
                "form": self.MONITORING_FORM_ID,
                "question": self.Q_OPTION_ID,
                "config": {"measure": "current_state", "group_by": "option"},
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["data"])

    def test_an_unconfigured_widget_previews_as_nothing_not_an_error(self):
        # The state every widget is in the moment it lands on the canvas.
        response = self.preview(
            {"id": -2, "type": "bar", "form": None, "question": None,
             "config": {}}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"])

    def test_string_filters_survive_the_preview_path_too(self):
        response = self.preview(
            {
                "id": -3,
                "type": "table",
                "form": self.MONITORING_FORM_ID,
                "question": None,
                "config": {
                    "columns": [{"key": "site", "source": "parent_name"}],
                    "page_size": 1,
                },
            },
            {"page": "2"},
        )
        self.assertEqual(response.status_code, 200)

    def test_dropping_the_id_does_not_weaken_the_family_rule(self):
        """The only check removed is the one about identity.

        Everything that stops a preview reaching outside what the author
        could have saved still applies.
        """
        outsider = Forms.objects.create(
            name="Someone else's", type=FormTypes.registration, version=1
        )
        response = self.preview(
            {"id": -4, "type": "bar", "form": outsider.id, "question": None,
             "config": {}}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "form")
