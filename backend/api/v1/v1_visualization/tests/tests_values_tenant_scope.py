from django.test.utils import override_settings
from rest_framework.test import APIClient

from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import FormStatus, QuestionTypes
from api.v1.v1_forms.models import (
    Forms, QuestionGroup, QuestionOptions, Questions,
)
from api.v1.v1_profile.models import Administration, Levels
from api.v1.v1_users.models import SystemUser, Tenant
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValuesTenantScopeTestCase(TenantIsolationTestCase):
    """The administration fallback must name the caller's own root.

    /visualization/values falls back to "the root administration" when
    the request carries no administration_id, which is every widget on
    a freshly opened dashboard. With more than one tenant in the
    database there is more than one root, and picking the wrong one is
    not an error anyone sees: the query still succeeds and every option
    comes back as 0. That is what this asks about — not whether one
    tenant can read another's rows, but whether a tenant can read its
    own.
    """

    BASE_URL = "/api/v1/visualization/values"

    def make_tenant(self, sub):
        fixture = super().make_tenant(sub)
        tenant = fixture["tenant"]
        form = Forms.objects.create(
            name=f"{sub}-registration",
            tenant=tenant,
            status=FormStatus.published,
        )
        group = QuestionGroup.objects.create(name="main", form=form)
        question = Questions.objects.create(
            form=form,
            question_group=group,
            order=1,
            label="Source type",
            name="source_type",
            type=QuestionTypes.option,
        )
        for order, value in enumerate(["borehole", "well"], start=1):
            QuestionOptions.objects.create(
                question=question,
                order=order,
                label=value.title(),
                value=value,
            )
        # One datapoint per tenant, so a cross-tenant read is visible as
        # a count rather than as an absence.
        datapoint = FormData.objects.create(
            name=f"{sub}-site",
            form=form,
            administration=fixture["child"],
            created_by=fixture["user"],
        )
        Answers.objects.create(
            data=datapoint,
            question=question,
            options=["borehole"],
            created_by=fixture["user"],
        )
        fixture.update({
            "reg_form": form,
            "question": question,
            "datapoint": datapoint,
        })
        return fixture

    def counts(self, response):
        self.assertEqual(response.status_code, 200)
        return {
            row["group"]: row["value"]
            for row in response.json()["data"]
        }

    def values_params(self, fixture):
        return {
            "form_id": fixture["reg_form"].id,
            "question_id": fixture["question"].id,
            "group_by": "option",
        }

    # -- The bug -------------------------------------------------------

    def test_each_tenant_counts_its_own_data_without_a_filter(self):
        """Both tenants see their own datapoint, not the other's root.

        `self.b` is created second, so its root administration has the
        higher id and an unordered, unscoped `.first()` never reaches
        it. Asserting on both tenants is what makes this a real test:
        checking only the first would pass against the bug.
        """
        for fixture in (self.a, self.b):
            with self.subTest(tenant=fixture["tenant"].subdomain):
                response = APIClient().get(
                    self.BASE_URL,
                    self.values_params(fixture),
                    **self.auth(fixture["user"]),
                )
                self.assertEqual(
                    self.counts(response),
                    {"borehole": 1, "well": 0},
                )

    @override_settings(BASE_DOMAIN="app.com")
    def test_host_resolves_the_root_for_an_anonymous_caller(self):
        """The workspace host scopes the fallback with no token at all.

        These endpoints are reachable anonymously, so the user's tenant
        cannot be the only source — a public dashboard on a workspace
        host has to resolve the same root a logged-in reader does.
        """
        for fixture in (self.a, self.b):
            sub = fixture["tenant"].subdomain
            with self.subTest(tenant=sub):
                response = APIClient().get(
                    self.BASE_URL,
                    self.values_params(fixture),
                    HTTP_HOST=f"{sub}.app.com",
                )
                self.assertEqual(
                    self.counts(response),
                    {"borehole": 1, "well": 0},
                )

    # -- The boundary --------------------------------------------------

    def test_form_from_another_tenant_is_not_found(self):
        """A form id names nothing outside the caller's workspace.

        Without this the fallback fix alone would still answer for
        tenant B's form — with tenant A's root, so a plausible 0 —
        rather than refusing it.
        """
        response = APIClient().get(
            self.BASE_URL,
            self.values_params(self.b),
            **self.auth(self.a["user"]),
        )
        self.assertEqual(response.status_code, 404)

    def test_explicit_administration_id_is_still_honoured(self):
        """An administration_id the caller sends is not overridden."""
        response = APIClient().get(
            self.BASE_URL,
            {
                **self.values_params(self.b),
                "administration_id": self.b["child"].id,
            },
            **self.auth(self.b["user"]),
        )
        self.assertEqual(
            self.counts(response), {"borehole": 1, "well": 0}
        )

    def test_foreign_administration_id_narrows_to_nothing(self):
        """Another workspace's administration id cannot widen the read.

        The caller-supplied administration_id is deliberately taken at
        face value rather than validated against the tenant: it only
        ever reaches apply_administration_filter, which narrows a
        queryset already rooted at the form — and the form is scoped
        above. So a foreign id can subtract rows, never add them, and
        the worst it produces is an empty chart of the caller's own
        options. This pins that, so the day administration_id gains a
        second use the boundary is not silently lost.
        """
        response = APIClient().get(
            self.BASE_URL,
            {
                **self.values_params(self.a),
                "administration_id": self.b["child"].id,
            },
            **self.auth(self.a["user"]),
        )
        self.assertEqual(
            self.counts(response), {"borehole": 0, "well": 0}
        )

    def test_tenant_without_a_root_administration_is_rejected(self):
        """No root to fall back to is a 400, not another tenant's root.

        Silently borrowing a root from whoever has one is how this bug
        behaved; refusing names the actual configuration gap.
        """
        tenant = Tenant.objects.create(subdomain="rootless")
        user = SystemUser.objects.create_superuser(
            email="admin@rootless.org", password="Secret#Pass123",
            first_name="R", last_name="R", tenant=tenant,
        )
        level = Levels.objects.create(name="", level=0, tenant=tenant)
        # A hierarchy that starts below the root: no parent IS NULL row.
        Administration.objects.create(
            parent=self.a["root"], level=level,
            name="orphan", tenant=tenant,
        )
        form = Forms.objects.create(
            name="rootless-form", tenant=tenant,
            status=FormStatus.published,
        )
        response = APIClient().get(
            self.BASE_URL,
            {"form_id": form.id},
            **self.auth(user),
        )
        self.assertEqual(response.status_code, 400)
