# =========================================================
# Dashboard builder: /manage/dashboards (VIZ-005)
# =========================================================
# Mirrors FormBuilderViewSet (FB-002): the queryset is scoped with
# for_user() so no action can reach a row outside the caller's tenant,
# and permissions come from a per-action map rather than a check
# scattered through each method.
#
# No pagination_class. VIZ-001 §6 says "paginated", but both merged
# consumers do Array.isArray(res.data) ? res.data : [], and
# DashboardBuilder resolves slug -> id by scanning the whole list, so
# an envelope would break the builder silently. See the spec, D-1.

from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from api.v1.v1_profile.constants import FeatureAccessTypes
from api.v1.v1_visualization.constants import (
    DashboardKind,
    DashboardStatus,
)
from api.v1.v1_visualization.dashboard_builder_serializers import (
    DashboardDetailSerializer,
    DashboardListSerializer,
    serialize_sources,
)
from api.v1.v1_visualization.dashboard_functions import (
    KIND_IDS,
    SLUG_PATTERN,
    apply_widgets,
    copy_name,
    copy_slug,
    derive_slug,
    suggest_slug,
    validate_dashboard_payload,
)
from api.v1.v1_visualization.dashboard_snapshot import build_snapshot
from api.v1.v1_visualization.embed_views import preview_url_for
from api.v1.v1_visualization.models import Dashboard, DashboardWidget
from utils.custom_permissions import DashboardAccess


class DenyUnmappedAction(BasePermission):
    """The safe reading of an action nobody mapped.

    Not exported: an action missing from ACCESS_PER_ACTION is a mistake
    in this file, and nowhere else has that map.
    """

    def has_permission(self, request, view):
        return False


# Every method carries its own @extend_schema rather than the class
# carrying one @extend_schema_view. FormBuilderViewSet can use the
# class-level form because its custom actions are @action-decorated and
# the router registers them; these are plain methods wired through
# as_view({...}) in urls.py, so drf-spectacular does not see them as
# actions and silently drops a class-level override ("argument was not
# found on view"). Decorating the method itself is what actually lands.
#
# "Manage Dashboards" mirrors "Manage Forms" (FB-002), which this viewset
# mirrors in every other respect. Untagged, these routes fall back to the
# first path segment and Swagger files the namespace under "v1".
MANAGE = "Manage Dashboards"

DASHBOARD_PK = OpenApiParameter(
    name="pk",
    required=True,
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    description="Dashboard id, scoped to the caller's workspace.",
)


@extend_schema_view(
    list=extend_schema(
        tags=[MANAGE],
        summary="List dashboards the caller may view",
        description=(
            "Bare array, not a paginated envelope (VIZ-005 D-1). Each row "
            "carries widget stubs (type and col_span) for the list "
            "screen's thumbnail strip."
        ),
        responses={200: DashboardListSerializer(many=True)},
    ),
    create=extend_schema(
        tags=[MANAGE],
        summary="Create a draft dashboard",
        description=(
            "The slug is derived server-side from the name unless one is "
            "supplied. `root_form` fixes the dashboard's data universe "
            "and cannot be changed afterwards (VIZ-001 D-3)."
        ),
        responses={201: DashboardDetailSerializer},
    ),
    retrieve=extend_schema(
        tags=[MANAGE],
        summary="Get a dashboard with its live widget rows",
        parameters=[DASHBOARD_PK],
        responses={200: DashboardDetailSerializer},
    ),
    update=extend_schema(
        tags=[MANAGE],
        summary="Replace a dashboard's settings and widgets",
        description=(
            "Edits the live rows, not the publish snapshot: a published "
            "dashboard keeps serving `published_config` until Publish is "
            "pressed again (VIZ-007 D-2). The slug is never re-derived — "
            "renaming is a cosmetic edit and the slug is the URL."
        ),
        parameters=[DASHBOARD_PK],
        responses={200: DashboardDetailSerializer},
    ),
    destroy=extend_schema(
        tags=[MANAGE],
        summary="Soft-delete a dashboard",
        parameters=[DASHBOARD_PK],
    ),
)
class DashboardBuilderViewSet(viewsets.ModelViewSet):
    # REST_FRAMEWORK.DEFAULT_PAGINATION_CLASS is LimitOffsetPagination
    # project-wide, so simply omitting pagination_class here would still
    # wrap list() in a {count, next, previous, results} envelope. This
    # explicit None is what actually produces the bare array the brief
    # describes and the merged builder requires.
    pagination_class = None

    def get_queryset(self):
        queryset = Dashboard.objects.for_user(self.request.user)
        queryset = queryset.select_related("root_form", "created_by")
        if self.action == "list":
            # Only list touches every row's widgets (for the thumbnail
            # stubs). update() serialises its response from this same
            # get_object() instance *after* apply_widgets rewrites the
            # widget rows — a prefetch cache filled here would still
            # hold the pre-save rows and make the PUT response show
            # stale widgets, so the other actions must not carry it.
            queryset = queryset.prefetch_related("widgets")
        return queryset.order_by("-id")

    def get_serializer_class(self):
        if self.action == "list":
            return DashboardListSerializer
        return DashboardDetailSerializer

    # One access type per action. FormBuilderViewSet spells the same
    # mapping out as full permission lists; this is the same rule in the
    # form that cannot drift between two near-identical entries.
    #
    # Opening the builder needs any of the four building accesses.
    # dashboard_view is deliberately not among them: after this change
    # it means "may read private published dashboards", which is a
    # consumer's permission and not a builder's.
    BUILDER_ACCESS = (
        FeatureAccessTypes.dashboard_create,
        FeatureAccessTypes.dashboard_edit,
        FeatureAccessTypes.dashboard_publish,
        FeatureAccessTypes.dashboard_delete,
    )

    ACCESS_PER_ACTION = {
        "list": BUILDER_ACCESS,
        "create": FeatureAccessTypes.dashboard_create,
        "retrieve": BUILDER_ACCESS,
        "update": FeatureAccessTypes.dashboard_edit,
        "destroy": FeatureAccessTypes.dashboard_delete,
        "sources": BUILDER_ACCESS,
        "publish": FeatureAccessTypes.dashboard_publish,
        "unpublish": FeatureAccessTypes.dashboard_publish,
        "visibility": FeatureAccessTypes.dashboard_publish,
        "duplicate": FeatureAccessTypes.dashboard_create,
        "embed_preview": FeatureAccessTypes.dashboard_edit,
    }

    def get_permissions(self):
        access = self.ACCESS_PER_ACTION.get(self.action)
        if access is None:
            # Deny rather than fall through to IsAuthenticated. An
            # action missing from the map above is an oversight, and the
            # safe reading of an oversight is "no access" rather than
            # "every signed-in user in the tenant".
            #
            # OPTIONS hits this branch too, deliberately. DRF's
            # ViewSetMixin.initialize_request sets self.action to the
            # literal string "metadata" for an OPTIONS request (it is
            # not left unset) — "metadata" is simply never a key in
            # ACCESS_PER_ACTION, so it falls into the same deny path as
            # any other unmapped action. That is fine to leave as-is:
            # this project has no corsheaders in INSTALLED_APPS, the
            # frontend is same-origin behind nginx, and nothing
            # preflights these paths, so 403-ing OPTIONS costs nothing.
            return [DenyUnmappedAction()]
        return [IsAuthenticated(), DashboardAccess(access)()]

    def create(self, request, *args, **kwargs):
        error = validate_dashboard_payload(request.data, request.user)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get("name")
        requested_slug = request.data.get("slug")
        slug = derive_slug(name, requested_slug)
        if not SLUG_PATTERN.match(slug):
            # Report whichever field actually produced the bad slug: a
            # client-supplied slug that fails the pattern is a "slug"
            # problem even though the derived-from-name path is what
            # usually trips this.
            field, message = (
                ("slug", "slug may only contain lowercase letters, "
                         "numbers and hyphens")
                if (requested_slug or "").strip()
                else ("name", "name must contain at least one letter "
                              "or digit")
            )
            return Response(
                {"message": message, "field": field},
                status=status.HTTP_400_BAD_REQUEST,
            )
        live = Dashboard.objects.for_user(request.user)
        if live.filter(slug=slug).exists():
            return Response(
                {
                    "message": (
                        "a dashboard with this name already exists"
                    ),
                    "suggested_slug": suggest_slug(slug, live),
                },
                status=status.HTTP_409_CONFLICT,
            )

        kind = KIND_IDS.get(
            request.data.get("kind"), DashboardKind.widgets
        )
        is_embed = kind == DashboardKind.embed
        dashboard = Dashboard.objects.create(
            name=name.strip(),
            slug=slug,
            description=request.data.get("description"),
            # Never from the payload: tenant comes from the
            # authenticated user, so a caller cannot plant a row in
            # someone else's workspace (MT-004).
            tenant=getattr(request.user, "tenant", None),
            kind=kind,
            root_form_id=(
                None if is_embed else request.data.get("root_form")
            ),
            embed_snippet=(
                request.data.get("embed_snippet") if is_embed else None
            ),
            created_by=request.user,
            # An embed has no data of ours to filter, so a stored filter
            # would be a setting with no effect.
            default_filters=(
                {} if is_embed
                else request.data.get("default_filters") or {}
            ),
        )
        return Response(
            DashboardDetailSerializer(instance=dashboard).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        dashboard = self.get_object()
        error = validate_dashboard_payload(
            request.data, request.user, dashboard=dashboard
        )
        if error:
            # Nothing has been written yet, and nothing will be: the
            # stored dashboard is byte-identical after a rejected save.
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            name = request.data.get("name")
            if name:
                # The slug is not re-derived. A dashboard's slug is its
                # URL and renaming is a cosmetic edit.
                dashboard.name = name.strip()
            dashboard.description = request.data.get("description")
            if dashboard.kind == DashboardKind.embed:
                snippet = request.data.get("embed_snippet")
                if snippet is not None:
                    dashboard.embed_snippet = snippet
                dashboard.default_filters = {}
            else:
                dashboard.default_filters = (
                    request.data.get("default_filters") or {}
                )
            dashboard.updated = timezone.now()
            dashboard.save()
            if dashboard.kind == DashboardKind.widgets:
                apply_widgets(
                    dashboard, request.data.get("widgets") or []
                )

        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    @extend_schema(
        tags=[MANAGE],
        summary="Publish — snapshot the widget rows into published_config",
        description=(
            "Revalidates before writing: `published_config` is what "
            "viewers read and nothing revalidates it downstream. A failed "
            "publish leaves the previous snapshot serving unchanged. "
            "Republishing re-snapshots."
        ),
        request=None,
        parameters=[DASHBOARD_PK],
        responses={200: DashboardDetailSerializer},
    )
    def publish(self, request, *args, **kwargs):
        dashboard = self.get_object()
        snapshot = build_snapshot(dashboard)
        # Revalidate through the *same* function PUT uses (spec D-3).
        # `published_config` is what viewers read and nothing
        # revalidates it downstream, so publishing is the last place a
        # broken dashboard can be stopped. Calling the save-time
        # validator rather than writing a stored-rows twin is what keeps
        # the two from drifting; tests_dashboard_snapshot pins the shape
        # compatibility that makes it possible.
        payload = {"name": dashboard.name}
        if dashboard.kind == DashboardKind.widgets:
            payload["widgets"] = snapshot["widgets"]
        error = validate_dashboard_payload(
            payload, request.user, dashboard=dashboard
        )
        if error:
            # Nothing written: status, published_config and
            # published_at are all exactly as they were, so a failed
            # republish keeps serving the last good snapshot.
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            dashboard.published_config = snapshot
            dashboard.status = DashboardStatus.published
            # Rewritten on every publish, unlike Forms.published_at
            # (spec D-2): a form's date is provenance, a dashboard's
            # answers "how fresh is what I am looking at".
            dashboard.published_at = timezone.now()
            dashboard.save()
        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    @extend_schema(
        tags=[MANAGE],
        summary="Unpublish — hide from the read namespace",
        description=(
            "Sets status back to draft. `published_config` is deliberately "
            "left in place as the record of what was last live; the read "
            "namespace filters on status, not on the field's presence. "
            "400 when the dashboard is not currently published."
        ),
        request=None,
        parameters=[DASHBOARD_PK],
        responses={200: DashboardDetailSerializer},
    )
    def unpublish(self, request, *args, **kwargs):
        dashboard = self.get_object()
        if dashboard.status != DashboardStatus.published:
            # 400 rather than an idempotent 204, following
            # FormBuilderViewSet.unpublish: this is a button-triggered
            # state transition, and a caller arriving from a stale UI is
            # better told than silently agreed with.
            return Response(
                {"message": "Dashboard is not published"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # published_config is deliberately left in place. The read
        # namespace filters on status, so clearing it would destroy the
        # record of what was last live without changing what any caller
        # can reach.
        dashboard.status = DashboardStatus.draft
        # Visibility goes with it. Without this, unpublishing a public
        # dashboard to fix a widget and republishing it would put it
        # back on the public web with nobody having decided to.
        dashboard.is_public = False
        dashboard.save(update_fields=["status", "is_public"])
        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    @extend_schema(
        tags=[MANAGE],
        summary="Set whether a dashboard is publicly readable",
        description=(
            "Public dashboards are readable without a token on this "
            "workspace's host. Only a published dashboard can be made "
            "public: on a draft the flag would have no observable "
            "effect, and allowing it would make Publish the button "
            "that exposes a dashboard to the internet."
        ),
        request=None,
        parameters=[DASHBOARD_PK],
        responses=DashboardDetailSerializer,
    )
    def visibility(self, request, *args, **kwargs):
        dashboard = self.get_object()
        is_public = request.data.get("is_public")
        if not isinstance(is_public, bool):
            return Response(
                {"message": "is_public must be true or false"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Going private is never refused, even when it changes nothing.
        # The one action whose purpose is reducing exposure must not
        # fail on a technicality.
        if is_public and dashboard.status != DashboardStatus.published:
            return Response(
                {"message": "Publish the dashboard before making it public"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dashboard.is_public = is_public
        dashboard.save(update_fields=["is_public"])
        return Response(
            DashboardDetailSerializer(instance=dashboard).data
        )

    @extend_schema(
        tags=[MANAGE],
        summary="Duplicate a dashboard as a new draft",
        description=(
            "The copy belongs to the caller's workspace, never the "
            "source's (MT-004), and carries no publication history of "
            "its own."
        ),
        request=None,
        parameters=[DASHBOARD_PK],
        responses={201: DashboardListSerializer},
    )
    def duplicate(self, request, *args, **kwargs):
        source = self.get_object()
        live = Dashboard.objects.for_user(request.user)
        with transaction.atomic():
            clone = Dashboard.objects.create(
                name=copy_name(source.name),
                slug=copy_slug(source.slug, live),
                description=source.description,
                # From the caller, never copied from the source: a
                # duplicate must not be able to move a dashboard into
                # another workspace (MT-004).
                tenant=getattr(request.user, "tenant", None),
                kind=source.kind,
                root_form=source.root_form,
                embed_snippet=source.embed_snippet,
                created_by=request.user,
                # Copied, not shared: the source's dict must not become
                # reachable through two rows.
                default_filters=dict(source.default_filters or {}),
                # A clone is a draft with no publication history of its
                # own. published_config and published_at are model
                # defaults, spelled out here because dropping them is
                # the point of the operation.
                status=DashboardStatus.draft,
                published_config=None,
                published_at=None,
            )
            DashboardWidget.objects.bulk_create(
                [
                    DashboardWidget(
                        dashboard=clone,
                        order=widget.order,
                        type=widget.type,
                        col_span=widget.col_span,
                        title=widget.title,
                        color=widget.color,
                        form_id=widget.form_id,
                        question_id=widget.question_id,
                        config=widget.config,
                    )
                    for widget in source.widgets.order_by("order", "id")
                ]
            )
        return Response(
            DashboardListSerializer(instance=clone).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=[MANAGE],
        summary="Mint an embed URL for unsaved markup",
        description=(
            "Preview has to show what a viewer will see, and a viewer "
            "sees the snippet running on EMBED_HOST rather than in this "
            "application's origin. Unsaved markup has no published "
            "snapshot to serve, so it is parked in the cache behind a "
            "single-use key and the signed URL names that key. 503 when "
            "EMBED_HOST is unconfigured, because there is nowhere safe "
            "to render it."
        ),
        parameters=[DASHBOARD_PK],
    )
    def embed_preview(self, request, *args, **kwargs):
        dashboard = self.get_object()
        if dashboard.kind != DashboardKind.embed:
            return Response(
                {"message": "not an embedded dashboard"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        snippet = request.data.get("embed_snippet")
        if not isinstance(snippet, str) or not snippet.strip():
            return Response(
                {"message": "embed_snippet is required",
                 "field": "embed_snippet"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = preview_url_for(snippet)
        if url is None:
            return Response(
                {"message": "Embedding is not configured for this "
                            "deployment"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"embed_url": url})

    @extend_schema(
        tags=[MANAGE],
        summary="Forms and questions a widget here may bind to",
        description=(
            "The family boundary as the builder sees it: the root "
            "registration form plus its monitoring forms. A form absent "
            "here is rejected on save."
        ),
        parameters=[DASHBOARD_PK],
    )
    def sources(self, request, *args, **kwargs):
        dashboard = self.get_object()
        if dashboard.kind == DashboardKind.embed:
            # Spec D-7: an embed has no form family, and there is
            # nothing truthful to put in the response. Not
            # {"forms": []} -- an empty collection reads as "this
            # workspace has no forms" and sends the reader to debug the
            # wrong thing.
            return Response(
                {"message": "an embedded dashboard has no form sources"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # This endpoint IS the family boundary as the UI sees it: if a
        # form is not here the builder cannot offer it, and if it
        # somehow does, validate_dashboard_payload rejects it on save.
        return Response(serialize_sources(dashboard, request.user))
