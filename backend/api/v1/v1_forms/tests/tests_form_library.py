from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import (
    FormStatus,
    FormTypes,
    QuestionTypes,
)
from api.v1.v1_forms.models import (
    FormCategory,
    Forms,
    QuestionGroup,
    Questions,
)
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    UserRole,
)
from api.v1.v1_users.models import SystemUser, Tenant


def _login(client, email="admin@akvo.org", password="Test105*"):
    res = client.post(
        "/api/v1/login",
        {"email": email, "password": password},
        content_type="application/json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {res.json().get('token')}"}


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormLibraryTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder", "--repeat", 3)
        call_command("default_roles_seeder", "--test")
        call_command("form_seeder", "--test")

        self.header = _login(self.client)
        self.admin = SystemUser.objects.filter(email="admin@akvo.org").first()

        # A curator: a platform admin (tenant-less), which IsCurator accepts
        # and which can authenticate in the single-host test environment.
        curator = SystemUser.objects.create_user(
            email="curator@akvo.org", password="Test105*"
        )
        curator.is_platform_admin = True
        curator.save()
        self.curator = curator
        self.curator_header = _login(self.client, "curator@akvo.org")

    # ── helpers ───────────────────────────────────

    def _make_family(
        self, tenant, name, status=FormStatus.published, template=False
    ):
        # A template is just a tenant-less form tagged meta.template; a
        # workspace form carries no such tag and belongs to a tenant.
        reg = Forms.objects.create(
            name=name,
            type=FormTypes.registration,
            status=status,
            tenant=None if template else tenant,
            meta={"template": True} if template else None,
        )
        g = QuestionGroup.objects.create(
            form=reg, name="g_" + name, label="G", order=1
        )
        Questions.objects.create(
            form=reg,
            question_group=g,
            name="q_" + name,
            label="Q",
            type=QuestionTypes.input,
            order=1,
        )
        child = Forms.objects.create(
            name=name + " Monitoring",
            type=FormTypes.monitoring,
            status=FormStatus.published,
            tenant=None if template else tenant,
            parent=reg,
        )
        cg = QuestionGroup.objects.create(
            form=child, name="cg_" + name, label="CG", order=1
        )
        Questions.objects.create(
            form=child,
            question_group=cg,
            name="cq_" + name,
            label="CQ",
            type=QuestionTypes.date,
            order=1,
        )
        return reg, child

    def _user_with_access(self, email, accesses):
        user = SystemUser.objects.create_user(email=email, password="Test105*")
        level = Levels.objects.first()
        role = Role.objects.create(
            name="role_" + email, administration_level=level
        )
        for acc in accesses:
            role.role_role_feature_access.create(
                type=FeatureTypes.form_builder, access=acc
            )
        adm = Administration.objects.first()
        UserRole.objects.create(user=user, role=role, administration=adm)
        return _login(self.client, email, "Test105*")

    # ── browse / isolation ────────────────────────

    def test_library_lists_only_published_library_registrations(self):
        tpl_reg, _ = self._make_family(None, "JMP WASH", template=True)
        self._make_family(
            None, "Draft Template", status=FormStatus.draft, template=True
        )
        # An ordinary workspace form must not leak into the library.
        self._make_family(self.admin.tenant, "Workspace Form")

        res = self.client.get("/api/v1/manage/forms/library", **self.header)
        self.assertEqual(res.status_code, 200)
        ids = [row["id"] for row in res.json()["data"]]
        self.assertIn(tpl_reg.id, ids)
        names = [row["name"] for row in res.json()["data"]]
        self.assertNotIn("Draft Template", names)
        self.assertNotIn("Workspace Form", names)
        # monitoring children never appear as their own row
        self.assertNotIn("JMP WASH Monitoring", names)
        row = next(r for r in res.json()["data"] if r["id"] == tpl_reg.id)
        self.assertEqual(row["monitoring_count"], 1)

    def test_library_template_absent_from_manage_forms(self):
        tpl_reg, _ = self._make_family(None, "Hidden Template", template=True)
        res = self.client.get("/api/v1/manage/forms", **self.header)
        body = res.json()["data"] if isinstance(res.json(), dict) else []
        all_ids = []
        for row in body:
            all_ids.append(row["id"])
            all_ids.extend(c["id"] for c in row.get("children", []))
        self.assertNotIn(tpl_reg.id, all_ids)

    # ── use (family clone) ────────────────────────

    def test_use_clones_family_into_caller_tenant(self):
        tpl_reg, tpl_child = self._make_family(None, "Use Me", template=True)

        res = self.client.post(
            f"/api/v1/manage/forms/library/{tpl_reg.id}/use", **self.header
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        new_reg = Forms.objects.get(pk=body["registration"]["id"])
        self.assertEqual(len(body["monitoring"]), 1)
        new_child = Forms.objects.get(pk=body["monitoring"][0]["id"])

        # new forms belong to the caller's tenant, are drafts, carry no
        # template flag, and form a real family.
        self.assertEqual(new_reg.tenant_id, new_reg.created_by.tenant_id)
        self.assertIsNone(new_reg.meta.get("template"))
        self.assertEqual(new_reg.status, FormStatus.draft)
        self.assertNotEqual(new_reg.id, tpl_reg.id)
        self.assertEqual(new_child.parent_id, new_reg.id)
        self.assertEqual(new_child.tenant_id, new_reg.tenant_id)
        # provenance stamped, no runtime link
        self.assertEqual(new_reg.meta["copied_from"]["form_id"], tpl_reg.id)

        # template untouched, import_count bumped
        tpl_reg.refresh_from_db()
        self.assertEqual(tpl_reg.import_count, 1)
        self.assertEqual(tpl_reg.meta["template"], True)
        self.assertEqual(tpl_child.parent_id, tpl_reg.id)

        # the clone (meta.copied_from, a non-null JSON object without the
        # template key) must appear in Manage Forms -- a naive
        # exclude(meta__template=True) would drop it via SQL NULL semantics.
        res = self.client.get("/api/v1/manage/forms", **self.header)
        ids = [row["id"] for row in res.json()["data"]]
        self.assertIn(new_reg.id, ids)

    def test_use_requires_form_create(self):
        tpl_reg, _ = self._make_family(None, "Gated", template=True)
        viewer = self._user_with_access(
            "viewer@akvo.org", [FeatureAccessTypes.form_view]
        )
        res = self.client.post(
            f"/api/v1/manage/forms/library/{tpl_reg.id}/use", **viewer
        )
        self.assertEqual(res.status_code, 403)

    # ── promote (Path 1) ──────────────────────────

    def test_promote_creates_family_in_library(self):
        # Source lives in a REAL workspace tenant (not the tenant-less test
        # admin): promote must still land the template tenant-less, or no
        # curator could ever edit/delete it (for_user is tenant-NULL).
        source_tenant = Tenant.objects.create(subdomain="django42")
        src_reg, src_child = self._make_family(source_tenant, "Promote Src")
        cat = FormCategory.objects.create(name="WASH", slug="wash")

        res = self.client.post(
            "/api/v1/manage/library/promote",
            {"source_form_id": src_reg.id, "category_ids": [cat.id]},
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 201)
        new_id = res.json()["id"]
        new_reg = Forms.objects.get(pk=new_id)
        self.assertIsNone(new_reg.tenant_id)
        self.assertEqual(new_reg.meta["template"], True)
        self.assertEqual(new_reg.status, FormStatus.published)
        self.assertEqual(new_reg.name, "Promote Src")
        self.assertEqual(new_reg.meta["source"]["form_id"], src_reg.id)
        self.assertEqual(
            list(new_reg.categories.values_list("id", flat=True)), [cat.id]
        )
        # the monitoring child came along, re-pointed AND tenant-less too
        child = new_reg.children.first()
        self.assertIsNotNone(child)
        self.assertEqual(child.type, FormTypes.monitoring)
        self.assertIsNone(child.tenant_id)

        # source family untouched (still owned by its workspace)
        src_reg.refresh_from_db()
        self.assertEqual(src_reg.tenant_id, source_tenant.id)
        self.assertEqual(src_child.parent_id, src_reg.id)

    def test_promote_forbidden_for_workspace_user(self):
        src_reg, _ = self._make_family(self.admin.tenant, "No Promote")
        res = self.client.post(
            "/api/v1/manage/library/promote",
            {"source_form_id": src_reg.id},
            content_type="application/json",
            **self.header,  # workspace super admin, not a curator
        )
        self.assertEqual(res.status_code, 403)

    # ── categories ────────────────────────────────

    def test_category_list_open_create_curator_only(self):
        FormCategory.objects.create(name="Agriculture", slug="agriculture")
        viewer = self._user_with_access(
            "cat_viewer@akvo.org", [FeatureAccessTypes.form_view]
        )
        # a form-builder user can read the filter list
        res = self.client.get("/api/v1/manage/form-categories", **viewer)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        # but cannot create one
        res = self.client.post(
            "/api/v1/manage/form-categories",
            {"name": "Health", "slug": "health"},
            content_type="application/json",
            **viewer,
        )
        self.assertEqual(res.status_code, 403)
        # the curator can
        res = self.client.post(
            "/api/v1/manage/form-categories",
            {"name": "Health", "slug": "health"},
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 201)

    def test_category_delete_then_recreate_same_name(self):
        res = self.client.post(
            "/api/v1/manage/form-categories",
            {"name": "Sanitation"},
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 201)
        cat_id = res.json()["id"]
        self.assertEqual(res.json()["slug"], "sanitation")
        res = self.client.delete(
            f"/api/v1/manage/form-categories/{cat_id}",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 204)
        # Re-creating the same name must not 500 on the unique constraint.
        res = self.client.post(
            "/api/v1/manage/form-categories",
            {"name": "Sanitation"},
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 201)

    def test_promote_rejects_draft_source(self):
        src_reg, _ = self._make_family(
            self.admin.tenant, "Draft Src", status=FormStatus.draft
        )
        res = self.client.post(
            "/api/v1/manage/library/promote",
            {"source_form_id": src_reg.id},
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 404)

    def test_unauthenticated_cannot_browse(self):
        res = self.client.get("/api/v1/manage/forms/library")
        self.assertIn(res.status_code, (401, 403))

    # ── authoring (Path 2 / curator bypass) ───────

    def _registration_payload(self, name):
        return {
            "name": name,
            "type": 1,
            "approval_instructions": None,
            "parent": None,
            "question_group": [
                {
                    "id": None,
                    "name": "grp",
                    "label": "Group",
                    "order": 1,
                    "repeatable": False,
                    "repeat_text": None,
                    "question": [
                        {
                            "id": None,
                            "order": 1,
                            "label": "Name",
                            "short_label": None,
                            "name": "q_name",
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
            ],
        }

    def test_curator_authored_registration_is_a_template(self):
        # A tenant-less platform admin passes the Form Builder gate (bypass)
        # and the new registration is tagged as a Library template.
        res = self.client.post(
            "/api/v1/manage/forms",
            self._registration_payload("From Scratch Template"),
            content_type="application/json",
            **self.curator_header,
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(name="From Scratch Template")
        self.assertIsNone(form.tenant_id)
        self.assertEqual(form.meta["template"], True)

    def test_workspace_create_is_not_a_template(self):
        creator = self._user_with_access(
            "creator@akvo.org", [FeatureAccessTypes.form_create]
        )
        res = self.client.post(
            "/api/v1/manage/forms",
            self._registration_payload("Ordinary Workspace Form"),
            content_type="application/json",
            **creator,
        )
        self.assertEqual(res.status_code, 201)
        form = Forms.objects.get(name="Ordinary Workspace Form")
        self.assertIsNone(form.meta)
