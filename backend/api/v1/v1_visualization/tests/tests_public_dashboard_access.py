import json

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_profile.models import (
    Administration,
    Role,
    RoleFeatureAccess,
    UserRole,
)
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from api.v1.v1_users.models import SystemUser, Tenant
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_visualization.models import Dashboard
from api.v1.v1_visualization.public_scope import allowlist_from
from utils.tenant_test_case import TenantIsolationTestCase


@override_settings(USE_TZ=False)
class PublicEndpointAccessTestCase(TestCase, ProfileTestHelperMixin):
    """An anonymous caller may only ask what the snapshot names."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_public@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        # create_user() never assigns a tenant, so it defaults to
        # None. resolve_view_scope's anonymous path resolves the
        # single-host tenant through public_tenant(), which returns
        # the one real Tenant row the seeders leave behind — so the
        # dashboard has to sit on that same row or no anonymous
        # lookup will ever find it.
        self.user.tenant = Tenant.objects.get()
        self.user.save()
        self.root = Forms.objects.get(pk=6001)
        # form_seeder --test leaves forms tenant-less, but
        # tenant_scoped_forms() filters by tenant once resolve_view_
        # scope hands back a concrete tenant (which it always does for
        # an anonymous, single-host request). Without this the form
        # itself 404s even once the dashboard lookup succeeds.
        self.root.tenant = self.user.tenant
        self.root.save()
        # Form 5 ("Test Form 5") is real, seeded by
        # form_seeder --test, and never named in this
        # dashboard's snapshot. Tenant-scoped the same way as
        # self.root: if it weren't, a form check_ids regression
        # would still 404 via tenant_scoped_forms downstream, and
        # test_a_form_not_on_the_dashboard_is_404 would pass for
        # the wrong reason.
        self.off_dashboard_form = Forms.objects.get(pk=5)
        self.off_dashboard_form.tenant = self.user.tenant
        self.off_dashboard_form.save()
        # Same gap, one level up: resolve_default_administration_id
        # falls back to the tenant's root administration, and that
        # root is tenant-less coming out of the seeder too.
        Administration.objects.filter(parent__isnull=True).update(
            tenant=self.user.tenant
        )
        # A second, real question on the root form that the
        # dashboard's snapshot never references. An id that does not
        # exist at all (e.g. 600199) can't stand in for "on the form
        # but off the dashboard": ValuesFilterSerializer.validate()
        # already 400s a question_id that isn't on form_id, before
        # check_ids ever runs, so it would only prove the serializer
        # still works — not that check_ids does.
        self.off_dashboard_question = Questions.objects.create(
            id=600105,
            form=self.root,
            question_group=Questions.objects.get(
                pk=600102
            ).question_group,
            order=5,
            label="Off dashboard metric",
            name="off_dashboard_metric",
            type=QuestionTypes.number,
        )
        self.dashboard = Dashboard.objects.create(
            name="Water Points",
            slug="water-points",
            root_form=self.root,
            tenant=self.user.tenant,
            created_by=self.user,
            status=DashboardStatus.published,
            is_public=True,
            published_config={
                "default_filters": {},
                "widgets": [
                    {
                        "id": 1,
                        "order": 1,
                        "type": "bar",
                        "col_span": 12,
                        "title": "By status",
                        "color": None,
                        "form": 6001,
                        "question": 600102,
                        "config": {"group_by": "option"},
                    },
                    # Names form 6002 on the snapshot so an escalation
                    # request may use it as monitoring_form_id. No
                    # question here: the escalation tests below only
                    # need columns=name:parent_name (no qid) for the
                    # allowed case, and reuse the already-off-dashboard
                    # 600105 for the negative ones.
                    {
                        "id": 2,
                        "order": 2,
                        "type": "table",
                        "col_span": 12,
                        "title": "Escalation",
                        "color": None,
                        "form": 6002,
                        "question": None,
                        "config": {},
                    },
                ],
            },
        )

    def values(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get("/api/v1/visualization/values", params)

    def escalation(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get(
            "/api/v1/visualization/escalation/6001", params
        )

    def formula(self, **params):
        params.setdefault("dashboard_slug", "water-points")
        params.setdefault("group_by", "parent_id")
        return self.client.get(
            "/api/v1/visualization/values/formula", params
        )

    def geo(self, form_id, **params):
        params.setdefault("dashboard_slug", "water-points")
        return self.client.get(
            "/api/v1/maps/geolocation/{0}".format(form_id), params
        )

    def bucket_formula(self, question_id):
        return json.dumps({
            "buckets": [{
                "value": "Yes",
                "label": "Yes",
                "all_of": [{
                    "question_id": question_id,
                    "op": "option_equals",
                    "value": "Yes",
                }],
            }],
            "default": {"value": "_no_info", "label": "_no_info"},
        })

    def test_an_allowed_form_and_question_answer(self):
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 200)

    def test_a_form_not_on_the_dashboard_is_404(self):
        # off_dashboard_form (id 5) is real, tenant-scoped to
        # this test's tenant, and not named anywhere in this
        # dashboard's snapshot. No question_id: 6002 is now on
        # the dashboard too (added for the escalation tests
        # below), so a form/question pair built on 6002 would
        # 404 on the question branch of check_ids and leave the
        # form branch this test exists to guard unexercised.
        res = self.values(form_id=self.off_dashboard_form.id)
        self.assertEqual(res.status_code, 404)

    def test_a_question_not_on_the_dashboard_is_404(self):
        res = self.values(form_id=6001, question_id=600105)
        self.assertEqual(res.status_code, 404)

    def test_a_criteria_question_not_on_the_dashboard_is_404(self):
        res = self.values(
            form_id=6001,
            question_id=600102,
            criteria="option_equals:600105:Yes",
        )
        self.assertEqual(res.status_code, 404)

    def test_a_date_question_not_on_the_dashboard_is_404(self):
        res = self.values(
            form_id=6001, question_id=600102, date_question_id=600199
        )
        self.assertEqual(res.status_code, 404)

    def test_no_slug_is_404(self):
        res = self.client.get(
            "/api/v1/visualization/values",
            {"form_id": 6001, "question_id": 600102},
        )
        self.assertEqual(res.status_code, 404)

    def test_no_slug_with_a_bogus_form_id_is_404_not_400(self):
        """The scope check must run before the serializer.

        ValuesFilterSerializer.validate_form_id issues a tenant-
        unscoped existence query. If that ran before resolve_view_
        scope, an anonymous caller with no dashboard could tell
        "form not found" (400) from "no public dashboard" (404), and
        enumerate another workspace's form ids one guess at a time —
        no aggregates leak, but the schema does.
        """
        res = self.client.get(
            "/api/v1/visualization/values", {"form_id": 999999}
        )
        self.assertEqual(res.status_code, 404)

    def test_an_allowed_escalation_request_answers(self):
        res = self.escalation(
            monitoring_form_id=6002, columns="name:parent_name"
        )
        self.assertEqual(res.status_code, 200)

    def test_an_escalation_monitoring_form_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=9999, columns="name:parent_name"
        )
        self.assertEqual(res.status_code, 404)

    def test_an_escalation_column_question_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=6002,
            columns="measurement:answer:600105",
        )
        self.assertEqual(res.status_code, 404)

    def test_an_escalation_criteria_question_not_on_the_dashboard_is_404(
        self,
    ):
        res = self.escalation(
            monitoring_form_id=6002,
            columns="name:parent_name",
            criteria="option_equals:600105:Yes",
        )
        self.assertEqual(res.status_code, 404)

    def test_a_private_dashboard_serves_nothing(self):
        self.dashboard.is_public = False
        self.dashboard.save()
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 404)

    def test_a_draft_dashboard_serves_nothing(self):
        self.dashboard.status = DashboardStatus.draft
        self.dashboard.save()
        res = self.values(form_id=6001, question_id=600102)
        self.assertEqual(res.status_code, 404)

    def test_formula_with_an_allowed_question(self):
        res = self.formula(
            form_id=6001, formula=self.bucket_formula(600102)
        )
        self.assertEqual(res.status_code, 200)

    def test_formula_smuggling_a_foreign_question_is_404(self):
        res = self.formula(
            form_id=6001, formula=self.bucket_formula(600199)
        )
        self.assertEqual(res.status_code, 404)

    def test_formula_on_a_foreign_form_is_404(self):
        # off_dashboard_form (id 5) is real and tenant-scoped to
        # this test's tenant (see setUp), so a check_ids regression
        # would still reach tenant_scoped_forms and 404 there
        # instead -- a bogus id like 9999 would make that
        # indistinguishable. 6002 cannot be used here either: it is
        # already on this dashboard's snapshot (the escalation
        # widget names it), so check_ids would permit it.
        res = self.formula(
            form_id=self.off_dashboard_form.id,
            formula=self.bucket_formula(600102),
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_on_the_allowed_form(self):
        self.assertEqual(self.geo(6001).status_code, 200)

    def test_geolocation_on_a_foreign_form_is_404(self):
        # Same reasoning as test_formula_on_a_foreign_form_is_404.
        self.assertEqual(
            self.geo(self.off_dashboard_form.id).status_code, 404
        )

    def test_geolocation_with_a_foreign_monitoring_form_is_404(self):
        # monitoring_form_id only reaches a query filter when
        # from_date or to_date is also set, so it is never looked up
        # against the database either way -- check_ids is the only
        # thing that can reject it, and a bogus id proves that just
        # as well as a real off-dashboard one. 6002 is on this
        # dashboard's snapshot, so 9999 is used instead.
        res = self.geo(
            6001, include_monitoring="true", monitoring_form_id=9999
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_no_slug_is_404(self):
        # test_no_slug_is_404 covers /values only. The geolocation
        # endpoint has its own view with its own scope check ordered
        # before its serializer (GeolocationListView.get), so it
        # needs its own regression rather than inheriting /values'.
        res = self.client.get(
            "/api/v1/maps/geolocation/6001", {}
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_an_unparseable_monitoring_form_id_is_404(
        self,
    ):
        # Fix round 1: Allowlist.permits_form used to do a bare
        # int(form_id), and monitoring_form_id is the one id in this
        # module that reaches check_ids straight off the query string
        # with no serializer or int() coercion upstream (form_id is a
        # path int; the others are all validated fields). A
        # hand-crafted monitoring_form_id=abc raised ValueError and
        # 500'd a public page instead of 404ing like any other id
        # that is not on the dashboard.
        res = self.geo(6001, monitoring_form_id="abc")
        self.assertEqual(res.status_code, 404)

    def test_geolocation_with_an_empty_monitoring_form_id_is_404(self):
        res = self.geo(6001, monitoring_form_id="")
        self.assertEqual(res.status_code, 404)


@override_settings(USE_TZ=False)
class ReadNamespaceTierTestCase(TestCase, ProfileTestHelperMixin):
    """Anonymous, plain, and dashboard-holding callers (spec D-3)."""

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.owner = self.create_user(
            email="viz_tiers@akvo.org", role_level=self.IS_SUPER_ADMIN
        )
        # create_user() never assigns a tenant (see the identical note
        # in PublicEndpointAccessTestCase above). Anonymous requests
        # resolve to the single seeded Tenant row through
        # public_tenant(); without this, self.owner.tenant is None and
        # the dashboards below would sit on a different "tenant" than
        # the one anonymous callers are ever scoped to.
        self.owner.tenant = Tenant.objects.get()
        self.owner.save()
        root = Forms.objects.get(pk=6001)
        common = {
            "root_form": root,
            "tenant": self.owner.tenant,
            "created_by": self.owner,
            "status": DashboardStatus.published,
            "published_config": {"default_filters": {}, "widgets": []},
        }
        self.public = Dashboard.objects.create(
            name="Public", slug="public-one", is_public=True, **common
        )
        self.private = Dashboard.objects.create(
            name="Private", slug="private-one", is_public=False, **common
        )

    def slugs(self, **headers):
        res = self.client.get("/api/v1/dashboards", **headers)
        self.assertEqual(res.status_code, 200)
        return {row["slug"] for row in res.json()}

    def test_anonymous_sees_only_public(self):
        self.assertEqual(self.slugs(), {"public-one"})

    def test_anonymous_can_open_a_public_dashboard(self):
        res = self.client.get("/api/v1/dashboards/public-one")
        self.assertEqual(res.status_code, 200)

    def test_anonymous_cannot_open_a_private_dashboard(self):
        res = self.client.get("/api/v1/dashboards/private-one")
        self.assertEqual(res.status_code, 404)

    def test_a_dashboard_holder_sees_both(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(self.owner).access_token
        header = {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}
        self.assertEqual(
            self.slugs(**header), {"public-one", "private-one"}
        )

    def test_a_draft_is_never_listed(self):
        self.public.status = DashboardStatus.draft
        self.public.save()
        self.assertEqual(self.slugs(), set())

    def test_a_plain_signed_in_user_sees_only_public(self):
        # IS_ADMIN carries no dashboard_builder feature access (no
        # "<level> Admin" role is seeded here) and is not a superuser,
        # so this is the middle tier: signed in, but holding no access
        # on the feature at all. Deferred from Task 10 because the
        # View-only-is-a-consumer semantics this proves did not exist
        # until dashboard_view stopped implying builder access.
        from rest_framework_simplejwt.tokens import RefreshToken
        plain = self.create_user(
            email="viz_plain@akvo.org", role_level=self.IS_ADMIN
        )
        # create_user() never assigns a tenant either (see the same
        # note on self.owner above) — without this, for_user(plain)
        # filters on tenant IS NULL and matches nothing at all, proving
        # nothing about the View-only/no-access tier this test targets.
        plain.tenant = self.owner.tenant
        plain.save()
        token = RefreshToken.for_user(plain).access_token
        header = {"HTTP_AUTHORIZATION": "Bearer {0}".format(token)}
        self.assertEqual(self.slugs(**header), {"public-one"})


@override_settings(USE_TZ=False, BASE_DOMAIN="app.com")
class AnonymousHostBoundaryTestCase(TenantIsolationTestCase):
    """The anonymous branch's two guards, proven at the viewset layer.

    Fix round 1, Important 1 and 2: a deleted throwaway test proved the
    tenant filter caught a cross-tenant leak, but nothing committed
    replaced it; and the `tenant is None -> rows.none()` branch had no
    coverage at all, only Task 4's coverage of `public_tenant` itself.
    Both tenants share one dashboard slug on purpose — a guessable slug
    is the case that matters, not a coincidence.
    """

    def setUp(self):
        super().setUp()
        common = dict(
            slug="shared",
            status=DashboardStatus.published,
            is_public=True,
            published_config={"default_filters": {}, "widgets": []},
        )
        self.a_dashboard = Dashboard.objects.create(
            name="Acme dashboard",
            root_form=self.a["form"],
            tenant=self.a["tenant"],
            **common,
        )
        self.b_dashboard = Dashboard.objects.create(
            name="Beta dashboard",
            root_form=self.b["form"],
            tenant=self.b["tenant"],
            **common,
        )
        # A tenant-less row, the way pre-MT-002 data or a stray test
        # fixture would leave one. Only visible from here if the
        # `tenant is None` branch ever degrades to a `tenant=None`
        # filter instead of `rows.none()`.
        self.orphan_dashboard = Dashboard.objects.create(
            name="Orphan dashboard",
            slug="orphan",
            root_form=self.a["form"],
            tenant=None,
            status=DashboardStatus.published,
            is_public=True,
            published_config={"default_filters": {}, "widgets": []},
        )

    def test_each_host_lists_only_its_own_tenant(self):
        for fixture, other_name in (
            (self.a, "Beta dashboard"),
            (self.b, "Acme dashboard"),
        ):
            sub = fixture["tenant"].subdomain
            res = self.client.get(
                "/api/v1/dashboards", HTTP_HOST="{0}.app.com".format(sub)
            )
            self.assertEqual(res.status_code, 200)
            names = {row["name"] for row in res.json()}
            self.assertEqual(len(names), 1)
            self.assertNotIn(other_name, names)

    def test_each_host_resolves_its_own_dashboard_by_the_shared_slug(self):
        for fixture, expected_name in (
            (self.a, "Acme dashboard"),
            (self.b, "Beta dashboard"),
        ):
            sub = fixture["tenant"].subdomain
            res = self.client.get(
                "/api/v1/dashboards/shared",
                HTTP_HOST="{0}.app.com".format(sub),
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["name"], expected_name)

    def test_bare_base_domain_lists_nothing(self):
        res = self.client.get("/api/v1/dashboards", HTTP_HOST="app.com")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_bare_base_domain_slug_is_404(self):
        res = self.client.get(
            "/api/v1/dashboards/orphan", HTTP_HOST="app.com"
        )
        self.assertEqual(res.status_code, 404)


@override_settings(USE_TZ=False)
class NonSuperuserDashboardHolderTestCase(TenantIsolationTestCase):
    """`has_any_dashboard_access` proven against the real ORM traversal.

    Fix round 1, Minor: `test_a_dashboard_holder_sees_both` authenticates
    as a superuser, which short-circuits the helper before its
    `user_user_role` traversal ever runs. This holds a plain account
    with `dashboard_edit` — not `dashboard_view` — to prove the
    traversal itself resolves True, and that any access on the feature
    is enough (spec: Edit-but-not-View must still be able to open what
    it built).
    """

    def setUp(self):
        super().setUp()
        self.private = Dashboard.objects.create(
            name="Acme private",
            slug="acme-private-holder",
            root_form=self.a["form"],
            tenant=self.a["tenant"],
            status=DashboardStatus.published,
            is_public=False,
            published_config={"default_filters": {}, "widgets": []},
        )
        self.holder = SystemUser.objects.create_user(
            email="holder@acme.org",
            password="Secret#Pass123",
            first_name="Hold",
            last_name="Er",
            tenant=self.a["tenant"],
        )
        role = Role.objects.create(
            name="Dashboard editor", administration_level=self.a["level"]
        )
        RoleFeatureAccess.objects.create(
            role=role,
            type=FeatureTypes.dashboard_builder,
            access=FeatureAccessTypes.dashboard_edit,
        )
        UserRole.objects.create(
            user=self.holder, role=role, administration=self.a["root"]
        )

    def test_a_non_superuser_holder_reads_a_private_dashboard(self):
        res = self.client.get(
            "/api/v1/dashboards/acme-private-holder",
            **self.auth(self.holder),
        )
        self.assertEqual(res.status_code, 200)


@override_settings(USE_TZ=False, BASE_DOMAIN="app.com")
class CrossTenantIdEscalationTestCase(TenantIsolationTestCase):
    """CLEANUP-001's attack, replayed: can A walk B's ids by number?

    Every "foreign id is 404" test above (PublicEndpointAccessTestCase)
    reuses off_dashboard_form/off_dashboard_question from the SAME
    tenant as the dashboard, so it only proves the allowlist
    (check_ids) rejects an id the dashboard's own snapshot never named.
    It says nothing about a caller who holds a real, valid dashboard on
    tenant A's host and then names an id that belongs to tenant B —
    the previous public dashboard feature was deleted from this
    codebase for exactly that gap (doc/design/CLEANUP-001-remove-
    public-dashboard.md).

    That gap is closed twice over here: check_ids refuses any id
    outside the dashboard's own allowlist regardless of tenant, and
    tenant_scoped_forms/get_object_or_404 would refuse tenant B's form
    even if check_ids let it through. Each test below is proven
    against both guards independently (see task-16-report.md for the
    neuter/widen experiments) rather than assumed from reading the
    code.
    """

    def setUp(self):
        super().setUp()
        for fixture in (self.a, self.b):
            group = QuestionGroup.objects.create(
                form=fixture["form"], name="Group", order=1,
            )
            fixture["question"] = Questions.objects.create(
                form=fixture["form"],
                question_group=group,
                order=1,
                label="Metric",
                name="metric",
                type=QuestionTypes.number,
            )
        common = dict(
            status=DashboardStatus.published,
            is_public=True,
            published_config={"default_filters": {}, "widgets": []},
        )
        self.a_dashboard = Dashboard.objects.create(
            name="Acme dashboard",
            slug="acme-view",
            root_form=self.a["form"],
            tenant=self.a["tenant"],
            **common,
        )
        self.b_dashboard = Dashboard.objects.create(
            name="Beta dashboard",
            slug="beta-view",
            root_form=self.b["form"],
            tenant=self.b["tenant"],
            **common,
        )

    def get(self, path, **params):
        params.setdefault("dashboard_slug", "acme-view")
        return self.client.get(
            path, params, HTTP_HOST="acme.app.com",
        )

    def test_a_foreign_forms_id_on_values_is_404(self):
        # B's form is real and published, just not on A's dashboard
        # (whose own allowlist names only A's form). No question_id:
        # ValuesFilterSerializer.validate() requires question_id to
        # belong to form_id, so pairing B's form with no question is
        # what keeps this a pure form-id probe rather than a 400.
        res = self.get(
            "/api/v1/visualization/values", form_id=self.b["form"].id,
        )
        self.assertEqual(res.status_code, 404)

    def test_a_foreign_questions_id_on_values_is_404(self):
        # Same serializer constraint forces question_id to be paired
        # with its own form_id (B's), so this necessarily also names
        # a foreign form_id -- see task-16-report.md for why the
        # question branch of check_ids cannot be isolated from the
        # form branch on this endpoint.
        res = self.get(
            "/api/v1/visualization/values",
            form_id=self.b["form"].id,
            question_id=self.b["question"].id,
        )
        self.assertEqual(res.status_code, 404)

    def test_a_foreign_monitoring_form_id_on_geolocation_is_404(self):
        # form_id in the path is A's own, on A's dashboard -- only
        # monitoring_form_id is foreign. monitoring_form_id never
        # reaches a database lookup (see the identical case in
        # PublicEndpointAccessTestCase above), so check_ids is the
        # only guard that can reject it.
        res = self.get(
            "/api/v1/maps/geolocation/{0}".format(self.a["form"].id),
            monitoring_form_id=self.b["form"].id,
        )
        self.assertEqual(res.status_code, 404)

    def test_the_other_tenants_slug_is_404_on_this_host(self):
        # A slug is resolved by (slug, tenant) together, never by
        # slug alone -- Beta's own real, published, public slug
        # simply is not a row Acme's host can ever match.
        res = self.client.get(
            "/api/v1/dashboards/beta-view", HTTP_HOST="acme.app.com",
        )
        self.assertEqual(res.status_code, 404)


@override_settings(USE_TZ=False)
class PublicEmbedDashboardTestCase(TestCase, ProfileTestHelperMixin):
    """An embed's allowlist is empty — spec D-6.

    An embedded dashboard queries none of our data endpoints, so the
    set of ids an anonymous caller holding its slug may name is the
    empty set. Every data endpoint must refuse.
    """

    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.user = self.create_user(
            email="viz_public_embed@akvo.org",
            role_level=self.IS_SUPER_ADMIN,
        )
        # As in PublicEndpointAccessTestCase: the anonymous path
        # resolves the single-host tenant through public_tenant(), so
        # the dashboard has to sit on that same row.
        self.user.tenant = Tenant.objects.get()
        self.user.save()
        self.root = Forms.objects.get(pk=6001)
        self.root.tenant = self.user.tenant
        self.root.save()
        Administration.objects.filter(parent__isnull=True).update(
            tenant=self.user.tenant
        )
        self.dashboard = Dashboard.objects.create(
            name="Sales",
            slug="sales",
            kind=DashboardKind.embed,
            root_form=None,
            embed_snippet="<iframe src='https://app.powerbi.com/view?r=x'>"
                          "</iframe>",
            tenant=self.user.tenant,
            created_by=self.user,
            status=DashboardStatus.published,
            is_public=True,
            published_config={
                "embed_snippet": "<iframe src='https://app.powerbi.com/"
                                 "view?r=x'></iframe>"
            },
        )

    def test_values_is_404(self):
        res = self.client.get(
            "/api/v1/visualization/values",
            {"dashboard_slug": "sales", "form_id": 6001},
        )
        self.assertEqual(res.status_code, 404)

    def test_escalation_is_404(self):
        # monitoring_form_id and columns are required by
        # EscalationFilterSerializer, which runs before check_ids --
        # without them the endpoint answers 400 and the allowlist is
        # never consulted, so the test would pass for the wrong reason.
        res = self.client.get(
            "/api/v1/visualization/escalation/6001",
            {
                "dashboard_slug": "sales",
                "monitoring_form_id": 6002,
                "columns": "name:parent_name",
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_formula_is_404(self):
        res = self.client.get(
            "/api/v1/visualization/values/formula",
            {
                "dashboard_slug": "sales",
                "form_id": 6001,
                "group_by": "parent_id",
                # Required by FormulaValuesSerializer, which runs
                # before check_ids -- same reason as the escalation
                # case above.
                "formula": json.dumps({
                    "buckets": [{
                        "value": "Yes",
                        "label": "Yes",
                        "all_of": [{
                            "question_id": 600102,
                            "op": "option_equals",
                            "value": "Yes",
                        }],
                    }],
                    "default": {
                        "value": "_no_info", "label": "_no_info",
                    },
                }),
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_geolocation_is_404(self):
        res = self.client.get(
            "/api/v1/maps/geolocation/6001", {"dashboard_slug": "sales"}
        )
        self.assertEqual(res.status_code, 404)

    def test_a_null_root_form_admits_no_garbage_form_id(self):
        # The widgets branch builds its form set from root_form_id, and
        # `permits_form` resolves an unparseable id to None through
        # `_as_id` -- so a set that still contained None would answer
        # True for any garbage a caller typed. The
        # `dashboard_kind_matches_source` constraint keeps such a row
        # out of the database, so this is asserted against an unsaved
        # instance: the guard has to hold in the function that builds
        # the set, not by luck of what the table happens to allow.
        naked = Dashboard(
            kind=DashboardKind.widgets,
            root_form=None,
            published_config={},
        )
        self.assertFalse(allowlist_from(naked).permits_form("garbage"))
