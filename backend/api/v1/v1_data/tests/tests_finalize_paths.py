"""APP-517: every web publication path leaves the row with a written file.

Asserted on the stamp and the file, not on a mock, so a path that stops
calling `finalize()` fails here. The file is written when the request
commits, which a TestCase only does inside `captureOnCommitCallbacks`.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_profile.models import Administration

ANSWERS = [
    {"question": 101, "value": "Jane"},
    {"question": 102, "value": ["Male"]},
    {"question": 103, "value": 31208200175},
    {"question": 104, "value": 2},
    {"question": 105, "value": [6.2088, 106.8456]},
    {"question": 106, "value": ["Parent", "Children"]},
    {"question": 109, "value": 0},
]


@override_settings(USE_TZ=False, TEST_ENV=True)
@mock.patch("api.v1.v1_data.models.async_task")
class FinalizePathsTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.adm = Administration.objects.filter(level__level=2).first()
        login = self.client.post(
            "/api/v1/login",
            {"email": "admin@akvo.org", "password": "Test105*"},
            content_type="application/json",
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {login.json()['token']}"}

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch("utils.storage.STORAGE_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = Path(tmp.name) / "datapoints"

    def payload(self, uuid):
        return {
            "data": {
                "name": "Testing Data",
                "administration": self.adm.id,
                "geo": [6.2088, 106.8456],
                "uuid": uuid,
            },
            "answer": ANSWERS,
        }

    def send(self, method, url, body=None):
        with self.captureOnCommitCallbacks(execute=True):
            response = getattr(self.client, method)(
                url, body, content_type="application/json", **self.auth
            )
        self.assertEqual(response.status_code // 100, 2, response.content)
        return response

    def assert_file_written(self, uuid):
        data = FormData.objects.get(uuid=uuid, is_draft=False)
        self.assertIsNotNone(data.file_generated_at)
        self.assertTrue((self.folder / f"{uuid}.json").exists())
        return data

    def test_web_submit(self, _task):
        self.send("post", "/api/v1/form-data/1/", self.payload("web"))
        self.assert_file_written("web")

    def test_pending_form_submit_by_a_superadmin(self, _task):
        self.send("post", "/api/v1/form-pending-data/1", self.payload("sa"))
        self.assert_file_written("sa")

    def test_direct_edit_rewrites_the_file(self, _task):
        self.send("post", "/api/v1/form-data/1/", self.payload("edit"))
        first = self.assert_file_written("edit").file_generated_at
        self.send(
            "put",
            f"/api/v1/form-data/1?data_id="
            f"{FormData.objects.get(uuid='edit').id}",
            [{"question": 101, "value": "Jane Doe"}],
        )
        self.assertGreater(
            self.assert_file_written("edit").file_generated_at, first
        )

    def test_publishing_a_draft(self, _task):
        self.send(
            "post", "/api/v1/draft-submissions/1/", self.payload("draft")
        )
        draft = FormData.objects_draft.get(uuid="draft")
        self.send("post", f"/api/v1/publish-draft-submission/{draft.id}")
        self.assert_file_written("draft")
