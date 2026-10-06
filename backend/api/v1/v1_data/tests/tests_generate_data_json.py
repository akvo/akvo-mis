from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData


@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateDataJSONTestCase(TestCase):
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
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test")

        user_payload = {"email": "admin@akvo.org", "password": "Test105*"}
        user_response = self.client.post(
            "/api/v1/login", user_payload, content_type="application/json"
        )
        self.token = user_response.json().get("token")
        self.call_command("-r", 1)

        # The command deletes orphaned files: never point it at the real
        # storage folder from a test database (APP-517 D-7).
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch("utils.storage.STORAGE_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = Path(tmp.name) / "datapoints"
        self.published = FormData.objects.filter(
            is_pending=False, is_draft=False, form__parent__isnull=True
        )

    def test_writes_a_file_for_every_published_registration_row(self):
        self.assertTrue(self.published.exists())
        call_command("generate_data_json", "--test", 1)
        for data in self.published:
            self.assertTrue(
                (self.folder / f"{data.uuid}.json").exists(), data.uuid
            )
            self.assertIsNotNone(data.file_generated_at)

    def test_dry_run_writes_nothing(self):
        out = StringIO()
        call_command("generate_data_json", "--dry-run", stdout=out)
        self.assertFalse(self.folder.exists())
        self.assertIn(
            f"Would have rewritten {self.published.count()}", out.getvalue()
        )
        self.assertFalse(
            self.published.filter(file_generated_at__isnull=False).exists()
        )
