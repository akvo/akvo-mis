import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_users.models import SystemUser
from api.v1.v1_data.models import FormData
from api.v1.v1_profile.models import Administration


def _q_group():
    return [
        {
            "id": None,
            "name": "household_info",
            "label": "Household Information",
            "order": 1,
            "repeatable": False,
            "repeat_text": None,
            "question": [
                {
                    "id": None,
                    "order": 1,
                    "label": "Head of Household",
                    "short_label": None,
                    "name": "head_of_household",
                    "type": "input",
                    "meta": True,
                    "required": True,
                    "rule": None,
                    "dependency": None,
                    "dependency_rule": "AND",
                    "api": None,
                    "extra": None,
                    "tooltip": None,
                    "fn": None,
                    "pre": None,
                    "display_only": False,
                    "option": [],
                }
            ],
        }
    ]


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


@override_settings(USE_TZ=False, TEST_ENV=True)
class ManageFormListFiltersTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")
        with connection.cursor() as cur:
            for tbl in ["form", "question_group", "question", "option"]:
                cur.execute(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tbl}', 'id'),"
                    f"(SELECT COALESCE(MAX(id), 0) FROM \"{tbl}\") + 1,"
                    f"false)"
                )
        self.header = _login(self.client)
        self.admin = SystemUser.objects.filter(
            email="admin@akvo.org"
        ).first()

    # ── helpers ───────────────────────────────────

    def _create(self, name, ftype=1, parent=None):
        res = self.client.post(
            "/api/v1/manage/forms",
            json.dumps(
                {
                    "name": name,
                    "type": ftype,
                    "approval_instructions": None,
                    "parent": parent,
                    "question_group": _q_group(),
                }
            ),
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()["id"]

    def _publish(self, form_id):
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/publish",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)

    def _archive(self, form_id):
        res = self.client.post(
            f"/api/v1/manage/forms/{form_id}/archive",
            content_type="application/json",
            **self.header,
        )
        self.assertEqual(res.status_code, 200)

    def _list(self, query=""):
        res = self.client.get(
            f"/api/v1/manage/forms{query}", **self.header
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()["data"]

    def _ids(self, data):
        return [row["id"] for row in data]

    def _reg_with_child(self):
        """A published registration parent + one monitoring child."""
        reg = self._create("ZZ Registration Parent")
        self._publish(reg)
        child = self._create("ZZ Monitoring Child", ftype=2, parent=reg)
        return reg, child

    # ── status filter ─────────────────────────────

    def test_filter_status_draft(self):
        draft = self._create("ZZ Draft One")
        pub = self._create("ZZ Pub One")
        self._publish(pub)
        ids = self._ids(self._list("?status=draft"))
        self.assertIn(draft, ids)
        self.assertNotIn(pub, ids)

    def test_filter_status_published(self):
        draft = self._create("ZZ Draft Two")
        pub = self._create("ZZ Pub Two")
        self._publish(pub)
        ids = self._ids(self._list("?status=published"))
        self.assertIn(pub, ids)
        self.assertNotIn(draft, ids)

    # ── type filter / row shape (D-4) ─────────────

    def test_type_registration_excludes_children(self):
        reg, child = self._reg_with_child()
        data = self._list("?type=registration")
        ids = self._ids(data)
        self.assertIn(reg, ids)
        self.assertNotIn(child, ids)
        for row in data:
            self.assertFalse(row.get("children"))

    def test_type_monitoring_flattened_top_level(self):
        reg, child = self._reg_with_child()
        data = self._list("?type=monitoring")
        ids = self._ids(data)
        self.assertIn(child, ids)
        self.assertNotIn(reg, ids)
        row = next(r for r in data if r["id"] == child)
        self.assertEqual(row["parent"], reg)

    def test_all_mode_nests_children_under_parent(self):
        reg, child = self._reg_with_child()
        data = self._list("")
        ids = self._ids(data)
        self.assertIn(reg, ids)
        self.assertNotIn(child, ids)
        parent_row = next(r for r in data if r["id"] == reg)
        child_ids = [c["id"] for c in parent_row.get("children", [])]
        self.assertIn(child, child_ids)

    # ── search (D-5) ──────────────────────────────

    def test_search_matches_name(self):
        a = self._create("UniqueAlpha Form")
        b = self._create("Totally Different")
        ids = self._ids(self._list("?search=UniqueAlpha"))
        self.assertIn(a, ids)
        self.assertNotIn(b, ids)

    def test_search_child_returns_parent_as_container(self):
        reg = self._create("Plain Parent")
        self._publish(reg)
        child = self._create("Findme Monitoring", ftype=2, parent=reg)
        data = self._list("?search=Findme")
        parent_row = next((r for r in data if r["id"] == reg), None)
        self.assertIsNotNone(
            parent_row, "parent must be returned as a container"
        )
        child_ids = [c["id"] for c in parent_row.get("children", [])]
        self.assertIn(child, child_ids)

    # ── submission_count (T-2) ────────────────────

    def test_submission_count_in_payload(self):
        form_id = self._create("ZZ Count Form")
        form = Forms.objects.get(pk=form_id)
        adm = Administration.objects.filter(level__level=1).first()
        FormData.objects.create(
            form=form, name="S1", administration=adm, created_by=self.admin
        )
        row = next(r for r in self._list("?type=registration")
                   if r["id"] == form_id)
        self.assertEqual(row["submission_count"], 1)

    # ── archived tab (D-8) ────────────────────────

    def test_default_excludes_archived(self):
        form_id = self._create("ZZ To Archive")
        self._archive(form_id)
        self.assertNotIn(form_id, self._ids(self._list("?type=registration")))

    def test_archived_true_lists_archived_with_status(self):
        form_id = self._create("ZZ Archived View")
        self._archive(form_id)
        data = self._list("?archived=true")
        row = next((r for r in data if r["id"] == form_id), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "archived")
