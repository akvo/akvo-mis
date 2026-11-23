"""LP-004 — starter forms from the Form Library during onboarding.

Covers the three backend seams: the public catalogue endpoint
(GET /register/form-library), the register `meta.template_ids` bound, and the
clone step that runs at /register/configure.
"""
from unittest import mock

from django.core import signing
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import FormStatus, FormTypes, QuestionTypes
from api.v1.v1_forms.models import (
    FormCategory,
    Forms,
    QuestionGroup,
    Questions,
)
from api.v1.v1_profile.models import Levels
from api.v1.v1_users.models import Organisation, SystemUser, Tenant


def _template(
    name,
    categories=(),
    status=FormStatus.published,
    published_children=1,
):
    """A library registration template: tenant-less, meta.template, published.

    Mirrors the real shape (a question group + question, and N published
    monitoring children) so the catalogue counts and clone are exercised for
    real, not against empty shells.
    """
    reg = Forms.objects.create(
        name=name,
        type=FormTypes.registration,
        status=status,
        tenant=None,
        meta={"template": True},
    )
    group = QuestionGroup.objects.create(
        form=reg, name="g_" + name, label="G", order=1
    )
    Questions.objects.create(
        form=reg,
        question_group=group,
        name="q_" + name,
        label="Q",
        type=QuestionTypes.input,
        order=1,
    )
    for i in range(published_children):
        child = Forms.objects.create(
            name=f"{name} Monitoring {i}",
            type=FormTypes.monitoring,
            status=FormStatus.published,
            tenant=None,
            parent=reg,
        )
        child_group = QuestionGroup.objects.create(
            form=child, name=f"cg_{name}_{i}", label="CG", order=1
        )
        Questions.objects.create(
            form=child,
            question_group=child_group,
            name=f"cq_{name}_{i}",
            label="CQ",
            type=QuestionTypes.date,
            order=1,
        )
    if categories:
        reg.categories.set(categories)
    return reg


@override_settings(USE_TZ=False)
class FormLibraryEndpointTestCase(TestCase):
    """GET /register/form-library: the pre-auth starter-forms catalogue."""

    def get(self, host=None):
        extra = {"HTTP_HOST": host} if host else {}
        return self.client.get("/api/v1/register/form-library", **extra)

    def test_groups_published_templates_by_category_with_counts(self):
        wash = FormCategory.objects.create(name="WASH", slug="wash")
        agri = FormCategory.objects.create(
            name="Agriculture", slug="agriculture"
        )
        _template(
            "JMP WASH Household", categories=[wash], published_children=1
        )
        _template(
            "Water Point Mapping", categories=[wash], published_children=0
        )
        _template("Farm Census", categories=[agri], published_children=2)

        body = self.get().json()
        # Categories are sorted by name: Agriculture before WASH.
        self.assertEqual(
            [c["name"] for c in body["categories"]], ["Agriculture", "WASH"]
        )
        by_name = {c["name"]: c for c in body["categories"]}
        wash_templates = {
            t["name"]: t for t in by_name["WASH"]["templates"]
        }
        self.assertEqual(
            set(wash_templates), {"JMP WASH Household", "Water Point Mapping"}
        )
        self.assertEqual(
            wash_templates["JMP WASH Household"]["monitoring_count"], 1
        )
        self.assertEqual(
            wash_templates["Water Point Mapping"]["monitoring_count"], 0
        )
        self.assertEqual(
            by_name["Agriculture"]["templates"][0]["monitoring_count"], 2
        )
        # Never the question structure -- names / ids / counts only.
        self.assertEqual(
            set(wash_templates["JMP WASH Household"]),
            {"id", "name", "monitoring_count"},
        )

    def test_empty_and_uncategorised_are_omitted(self):
        FormCategory.objects.create(name="Empty", slug="empty")
        _template("Uncategorised Template", categories=[])
        self.assertEqual(self.get().json()["categories"], [])

    def test_drafts_and_workspace_forms_are_excluded(self):
        health = FormCategory.objects.create(name="Health", slug="health")
        _template(
            "Draft Template", categories=[health], status=FormStatus.draft
        )
        tenant = Tenant.objects.create(subdomain="acme", name="Acme")
        workspace_form = Forms.objects.create(
            name="Workspace Form",
            type=FormTypes.registration,
            status=FormStatus.published,
            tenant=tenant,
            meta=None,
        )
        workspace_form.categories.set([health])
        self.assertEqual(self.get().json()["categories"], [])

    def test_blocked_on_a_tenant_subdomain(self):
        # The host must resolve to a real workspace, or the tenant middleware
        # 404s it before the view runs; with a live tenant the request reaches
        # the view, which refuses the catalogue off the base domain.
        Tenant.objects.create(subdomain="acme", name="Acme", is_active=True)
        with override_settings(BASE_DOMAIN="app.com"):
            res = self.get(host="acme.app.com")
        self.assertEqual(res.status_code, 403)


@override_settings(USE_TZ=False)
class RegisterMetaTemplateIdsTestCase(TestCase):
    """POST /register bounds meta.template_ids (shape + length)."""

    def register(self, meta, subdomain="acme"):
        with mock.patch("api.v1.v1_users.views.send_email"):
            return self.client.post(
                "/api/v1/register",
                {
                    "email": "founder@acme.org",
                    "password": "Secret#Pass123",
                    "subdomain": subdomain,
                    "meta": meta,
                },
                content_type="application/json",
            )

    def test_valid_ids_accepted_and_stored_on_the_tenant(self):
        res = self.register({"template_ids": [1, 2, 3]})
        self.assertEqual(res.status_code, 200)
        tenant = Tenant.objects.get(subdomain="acme")
        self.assertEqual(tenant.meta["template_ids"], [1, 2, 3])

    def test_more_than_ten_is_rejected(self):
        self.assertEqual(
            self.register({"template_ids": list(range(1, 12))}).status_code,
            400,
        )

    def test_non_list_is_rejected(self):
        self.assertEqual(self.register({"template_ids": 5}).status_code, 400)

    def test_non_int_member_is_rejected(self):
        self.assertEqual(
            self.register({"template_ids": ["x"]}).status_code, 400
        )

    def test_boolean_member_is_rejected(self):
        self.assertEqual(
            self.register({"template_ids": [True]}).status_code, 400
        )

    def test_non_positive_member_is_rejected(self):
        self.assertEqual(
            self.register({"template_ids": [0]}).status_code, 400
        )


@override_settings(USE_TZ=False)
class ConfigureClonesStarterFormsTestCase(TestCase):
    """POST /register/configure clones the staged templates, resiliently."""

    config = {
        "first_name": "Ada",
        "last_name": "Founder",
        "level_0_name": "National",
        "root_unit_name": "Kenya",
    }

    def signup(self, meta, email="founder@acme.org", subdomain="acme"):
        with mock.patch("api.v1.v1_users.views.send_email"):
            self.client.post(
                "/api/v1/register",
                {
                    "email": email,
                    "password": "Secret#Pass123",
                    "subdomain": subdomain,
                    "meta": meta,
                },
                content_type="application/json",
            )
        user = SystemUser.objects.get(email=email)
        token = self.client.post(
            "/api/v1/register/activate",
            {"token": signing.dumps(user.pk)},
            content_type="application/json",
        ).json()["token"]
        return user, {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def configure(self, auth):
        return self.client.post(
            "/api/v1/register/configure",
            self.config,
            content_type="application/json",
            **auth,
        )

    def test_only_valid_published_templates_are_cloned_as_drafts(self):
        valid = _template("JMP WASH", published_children=1)
        draft = _template("Draft Template", status=FormStatus.draft)
        user, auth = self.signup(
            {"template_ids": [valid.id, draft.id, 999999]}
        )
        res = self.configure(auth)
        self.assertEqual(res.status_code, 200)

        cloned = Forms.objects.filter(tenant=user.tenant)
        registrations = cloned.filter(type=FormTypes.registration)
        # Only the valid published family cloned; draft + unknown id skipped.
        self.assertEqual(registrations.count(), 1)
        self.assertEqual(registrations.first().status, FormStatus.draft)
        # Its one published monitoring child came along, re-pointed and draft.
        children = cloned.filter(type=FormTypes.monitoring)
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first().parent_id, registrations.first().id)

    def test_clone_failure_still_configures_the_workspace(self):
        valid = _template("JMP WASH")
        user, auth = self.signup({"template_ids": [valid.id]})
        with mock.patch(
            "api.v1.v1_users.views.clone_family",
            side_effect=Exception("boom"),
        ):
            res = self.configure(auth)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["configured"])
        self.assertTrue(
            Levels.objects.filter(tenant=user.tenant, level=0).exists()
        )
        # The failed clone left nothing behind.
        self.assertEqual(
            Forms.objects.filter(tenant=user.tenant).count(), 0
        )

    def test_no_template_ids_clones_nothing(self):
        user, auth = self.signup({})
        self.assertEqual(self.configure(auth).status_code, 200)
        self.assertEqual(
            Forms.objects.filter(tenant=user.tenant).count(), 0
        )

    def test_starter_forms_keep_names_and_selection_order(self):
        # Two templates staged reversed, so the clone order is observable.
        first = _template("Agriculture Baseline", published_children=1)
        second = _template("WASH Household", published_children=0)
        user, auth = self.signup({"template_ids": [second.id, first.id]})
        self.assertEqual(self.configure(auth).status_code, 200)

        registrations = Forms.objects.filter(
            tenant=user.tenant, type=FormTypes.registration
        ).order_by("id")
        # Cloned in the visitor's order (second, then first), each keeping its
        # real name -- no " (Copy)" suffix.
        self.assertEqual(
            [r.name for r in registrations],
            ["WASH Household", "Agriculture Baseline"],
        )
        # The monitoring child keeps its real name too.
        child = Forms.objects.get(
            tenant=user.tenant, type=FormTypes.monitoring
        )
        self.assertEqual(child.name, "Agriculture Baseline Monitoring 0")

    def test_configure_seeds_organisation_from_meta_when_omitted(self):
        user, auth = self.signup({"org": "Rural Water Trust"})
        # self.config carries no `organisation`; configure must fall back to
        # the org the wizard staged on Tenant.meta, so the manual /configure
        # fallback path does not lose it.
        self.assertEqual(self.configure(auth).status_code, 200)
        self.assertTrue(
            Organisation.objects.filter(
                tenant=user.tenant, name="Rural Water Trust"
            ).exists()
        )
