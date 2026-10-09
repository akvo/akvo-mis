import logging
from unittest import mock
from django.test import TestCase, override_settings
from requests.exceptions import RequestException

from utils.matomo import (
    track_matomo_event,
    track_matomo_page_view,
    track_submission_task,
)


class MatomoServiceTestCase(TestCase):
    @override_settings(
        MATOMO_SITE_ID=None, MATOMO_URL="https://matomo.example.org"
    )
    @mock.patch("utils.matomo.requests.post")
    def test_matomo_disabled_when_site_id_none(self, mock_post):
        res = track_matomo_event(
            category="Data Submission",
            action="Mobile Sync",
            name="Survey Form",
        )
        self.assertFalse(res)
        mock_post.assert_not_called()

    @override_settings(MATOMO_SITE_ID=8, MATOMO_URL="")
    @mock.patch("utils.matomo.requests.post")
    def test_matomo_disabled_when_url_empty(self, mock_post):
        res = track_matomo_event(
            category="Data Submission",
            action="Mobile Sync",
        )
        self.assertFalse(res)
        mock_post.assert_not_called()

    @override_settings(
        MATOMO_SITE_ID=8,
        MATOMO_URL="https://matomo.cloud.akvo.org",
        MATOMO_AUTH_TOKEN="test-token-123",
        MATOMO_DIM_TENANT=1,
        MATOMO_DIM_SUBDOMAIN=2,
    )
    @mock.patch("utils.matomo.requests.post")
    def test_track_submission_task_mobile_payload(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = track_submission_task(
            tenant_name="Kenya Water",
            form_name="Water Point Survey",
            form_id=42,
            source="mobile",
            user_id="101",
            subdomain="kenya-water",
        )
        self.assertTrue(res)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://matomo.cloud.akvo.org/matomo.php")
        params = kwargs.get("params") or {}
        self.assertEqual(params.get("idsite"), 8)
        self.assertEqual(params.get("rec"), 1)
        self.assertEqual(params.get("apiv"), 1)
        self.assertEqual(params.get("send_image"), 0)
        self.assertEqual(params.get("e_c"), "Data Submission")
        self.assertEqual(params.get("e_a"), "Mobile Sync")
        self.assertEqual(params.get("e_k"), None)
        self.assertEqual(params.get("e_n"), "Water Point Survey")
        self.assertEqual(params.get("token_auth"), "test-token-123")
        self.assertEqual(params.get("uid"), "101")
        self.assertEqual(params.get("dimension1"), "Kenya Water")
        self.assertEqual(params.get("dimension2"), "kenya-water")
        self.assertEqual(kwargs.get("timeout"), 3)

    @override_settings(
        MATOMO_SITE_ID=8,
        MATOMO_URL="https://matomo.cloud.akvo.org",
        MATOMO_AUTH_TOKEN="test-token-123",
        MATOMO_DIM_TENANT=1,
        MATOMO_DIM_SUBDOMAIN=None,
    )
    @mock.patch("utils.matomo.requests.post")
    def test_track_submission_task_web_payload(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = track_submission_task(
            tenant_name="Uganda Health",
            form_name="Clinic Registration",
            form_id=99,
            source="web",
            user_id="202",
        )
        self.assertTrue(res)
        params = mock_post.call_args[1]["params"]
        self.assertEqual(params.get("e_c"), "Data Submission")
        self.assertEqual(params.get("e_a"), "Webform Submit")
        self.assertEqual(params.get("e_n"), "Clinic Registration")
        self.assertEqual(params.get("dimension1"), "Uganda Health")
        self.assertNotIn("dimension2", params)

    @override_settings(
        MATOMO_SITE_ID=8,
        MATOMO_URL="https://matomo.cloud.akvo.org",
        MATOMO_AUTH_TOKEN="test-token-123",
        MATOMO_DIM_TENANT=None,
    )
    @mock.patch("utils.matomo.requests.post")
    def test_track_submission_task_no_custom_dim_when_none(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        track_submission_task(
            tenant_name="Default Tenant",
            form_name="General Form",
            form_id=1,
            source="mobile",
        )
        params = mock_post.call_args[1]["params"]
        self.assertNotIn("dimension1", params)

    @override_settings(
        MATOMO_SITE_ID=8,
        MATOMO_URL="https://matomo.cloud.akvo.org",
    )
    @mock.patch("utils.matomo.requests.post")
    def test_track_matomo_page_view(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = track_matomo_page_view(
            url="https://kenya-water.akvo.org/forms",
            action_name="Forms List",
            tenant_name="Kenya Water",
            user_id="101",
        )
        self.assertTrue(res)
        params = mock_post.call_args[1]["params"]
        self.assertEqual(
            params.get("url"), "https://kenya-water.akvo.org/forms"
        )
        self.assertEqual(params.get("action_name"), "Forms List")

    @override_settings(
        MATOMO_SITE_ID=8,
        MATOMO_URL="https://matomo.cloud.akvo.org",
    )
    @mock.patch("utils.matomo.requests.post")
    def test_handles_request_exception_silently(self, mock_post):
        mock_post.side_effect = RequestException("Connection refused")
        with self.assertLogs("utils.matomo", level=logging.WARNING) as cm:
            res = track_matomo_event(
                category="Data Submission",
                action="Mobile Sync",
            )
            self.assertFalse(res)
            self.assertTrue(
                any(
                    "Matomo tracking request failed" in msg
                    for msg in cm.output
                )
            )
