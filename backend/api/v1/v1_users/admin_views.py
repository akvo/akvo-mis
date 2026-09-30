"""Platform console endpoints.

Every view here queries `Tenant.objects` directly rather than through
`for_user()`. That is deliberate and visible: an operator is
tenant-less, so `for_user` would filter on `tenant IS NULL` and return
nothing. Cross-tenant reading has to be opted into explicitly, and this
module is the only place it happens.

Nothing here returns a workspace's data. There is no delete endpoint
for datapoints or dashboards anywhere under /admin/ -- the absence is
the enforcement, not a flag.
"""
import logging
import os

from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.v1.v1_profile.models import Administration
from api.v1.v1_users.admin_serializers import (
    TENANT_STATES,
    OperatorInviteSerializer,
    OperatorSerializer,
    TenantFeaturesSerializer,
    TenantListSerializer,
    TenantRenameSerializer,
    TenantSummarySerializer,
    TenantUserSerializer,
)
from api.v1.v1_users.models import SystemUser, Tenant
# Imported by name rather than called through `views`, so that a test
# patching `admin_views.send_activation_email` patches what this module
# actually calls.
from api.v1.v1_users.views import send_activation_email
from api.v1.v1_visualization.models import Dashboard
from utils.custom_generator import sqlite_path
from utils.custom_permissions import IsPlatformAdmin

logger = logging.getLogger(__name__)

CONSOLE_TAG = ["Platform Console"]


def console_tenants():
    """Every workspace, deleted ones included.

    The console is the one reader that must see a deleted workspace:
    it is the only place its state can be explained.

    The prefetch is for `TenantListSerializer.get_name`, which reads the
    root administration unit of every row. Without it the cost of
    listing is one query per workspace.
    """
    return (
        Tenant.objects.all()
        .prefetch_related("administrations")
        .order_by("subdomain")
    )


def with_counts(queryset):
    """How much is in each workspace, annotated onto the rows.

    Every console endpoint that hands back a workspace uses this, not
    just the ones that list. The detail page assigns each response
    straight over the workspace it is displaying, so a reply without the
    counts does not merely omit them -- it blanks five stat tiles that
    were on screen a moment ago, beside a Delete button. Suspending a
    workspace and being told it holds no data is the opposite of what
    this console is for.

    Every Count carries distinct=True because the joins multiply:
    counting forms and users in the same query without it returns
    forms x users for both. The soft-delete filters are part of the
    count rather than applied afterwards, so a deleted datapoint is
    never counted and never has to be subtracted.

    The `_count` suffixes are not cosmetic -- Django refuses an
    annotation that shadows a field or reverse accessor, and three of
    these five are reverse accessors on Tenant. The serializer sources
    the plain wire names from these.
    """
    return queryset.annotate(
        users_count=Count(
            "users", distinct=True, filter=Q(users__deleted_at=None)
        ),
        forms_count=Count(
            "forms", distinct=True, filter=Q(forms__deleted_at=None)
        ),
        dashboards_count=Count(
            "dashboards", distinct=True,
            filter=Q(dashboards__deleted_at=None),
        ),
        datapoints_count=Count(
            "forms__form_form_data", distinct=True,
            filter=Q(forms__form_form_data__deleted_at=None),
        ),
        devices_count=Count("users__mobile_assignments", distinct=True),
    )


@extend_schema(responses={200: TenantListSerializer(many=True)},
               tags=CONSOLE_TAG, summary="List every workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def list_tenants(request, version):
    """Every workspace, optionally narrowed by name or by state.

    The state vocabulary is the one the serializer reports, not a
    second one invented here: a console that renders `state` and then
    filters by some other spelling would be a UI that cannot round-trip
    its own values.
    """
    queryset = console_tenants()
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(subdomain__icontains=search)
    state = request.query_params.get("state")
    if state:
        if state not in TENANT_STATES:
            # Refused rather than ignored, as an unknown feature key is.
            # Silently returning every workspace would read as "this
            # deployment has no suspended ones".
            return Response(
                {
                    "message": "Unknown state '{0}'. Accepted: {1}.".format(
                        state, ", ".join(sorted(TENANT_STATES))
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(**TENANT_STATES[state])
    return Response(
        TenantListSerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(responses={200: TenantSummarySerializer}, tags=CONSOLE_TAG,
               summary="One workspace, or soft-delete it")
@api_view(["GET", "DELETE"])
@permission_classes([IsPlatformAdmin])
def tenant_detail(request, version, tenant_id):
    # Annotated, because the console's detail page is six stat tiles
    # over this response. A DELETE answers with the same shape so the
    # page can render what it just changed without a second request.
    tenant = get_object_or_404(with_counts(console_tenants()), pk=tenant_id)
    if request.method == "DELETE":
        # Soft only. Every tenant FK is PROTECT, so a hard delete would
        # raise -- and making it work means flipping those to CASCADE
        # across every tenant-owned model, which is a separate and much
        # riskier piece of work.
        tenant.deleted_at = timezone.now()
        tenant.save(update_fields=["deleted_at"])
    return Response(
        TenantSummarySerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: TenantSummarySerializer}, tags=CONSOLE_TAG,
               summary="Suspend a workspace")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def deactivate_tenant(request, version, tenant_id):
    return _set_active(tenant_id, False)


@extend_schema(responses={200: TenantSummarySerializer}, tags=CONSOLE_TAG,
               summary="Restore a suspended workspace")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def activate_tenant(request, version, tenant_id):
    return _set_active(tenant_id, True)


def _set_active(tenant_id, active):
    tenant = get_object_or_404(with_counts(console_tenants()), pk=tenant_id)
    tenant.is_active = active
    tenant.save(update_fields=["is_active"])
    return Response(
        TenantSummarySerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(request=TenantFeaturesSerializer,
               responses={200: TenantSummarySerializer}, tags=CONSOLE_TAG,
               summary="Set a workspace's entitlements")
@api_view(["PUT"])
@permission_classes([IsPlatformAdmin])
def set_tenant_features(request, version, tenant_id):
    tenant = get_object_or_404(with_counts(console_tenants()), pk=tenant_id)
    serializer = TenantFeaturesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Merged rather than replaced: the console sends the switches it
    # knows about, and a flag added in a later release must not be
    # cleared by an older client that has never heard of it.
    features = dict(tenant.features or {})
    features.update(serializer.validated_data)
    tenant.features = features
    try:
        tenant.save(update_fields=["features"])
    except IntegrityError:
        return Response(
            {"message": "Could not save entitlements"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        TenantSummarySerializer(tenant).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: TenantSummarySerializer(many=True)},
               tags=CONSOLE_TAG, summary="Counts for every workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def tenants_summary(request, version):
    """How much is in each workspace, at a cost that does not grow.

    Every Count carries distinct=True because the joins multiply:
    counting forms and users in the same query without it returns
    forms x users for both. The soft-delete filters are part of the
    count rather than applied afterwards, so a deleted datapoint is
    never counted and never has to be subtracted.
    """
    queryset = with_counts(console_tenants())
    return Response(
        TenantSummarySerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


def rename_impact(tenant):
    """What renaming this workspace will break.

    Counted from the workspace rather than stated generally, because a
    dialog that names 23 devices is not clicked through the way a
    generic warning is.
    """
    # No mobile-device count either, and for a sharper reason than the
    # embeds below: the app is configured against the deployment's own
    # address, not a workspace's. `MobileFormSerializer.get_url` hands
    # devices `/form/<id>` rather than an absolute host, nothing under
    # `v1_mobile` builds a tenant URL, and the shipped build params
    # document `serverURL` as `https://<your-domain>/api/v1/device`. A
    # device syncing against the base domain reaches a request whose
    # `tenant` is None, so the middleware's host check is skipped and
    # what partitions the reply is the token's assignment -- which a
    # rename does not touch. The dialog used to say every enrolled
    # device would stop syncing and need re-enrolling by hand, the
    # most alarming line it had, describing field work that does not
    # exist. See `test_a_device_on_the_base_domain_survives_a_rename`.
    #
    # No embedded-dashboard count, and that absence is a finding rather
    # than an omission. The spec listed third-party `<iframe>`s as
    # possible breakage but said the embed document "deliberately knows
    # no subdomain, so this may survive; it must be confirmed during
    # implementation rather than assumed." Confirmed: `embed_url_for`
    # builds `EMBED_HOST/api/v1/embed/<token>`, and the token carries a
    # dashboard id, never an address. A rename leaves it byte for byte
    # the same, so warning about it told an operator that a rename
    # breaks something it does not touch. See `tests_admin_rename`.
    published = Dashboard.objects.filter(
        tenant=tenant, deleted_at=None
    ).exclude(published_config=None)
    return {
        # The two dashboard counts partition the published set, and
        # that is deliberate. They used to overlap -- every published
        # dashboard was counted as a link, and one carrying a snippet
        # was counted again as an embed -- so the dialog claimed more
        # would break than the workspace contains.
        #
        # They are reported apart rather than summed because the
        # audiences differ. An internal link breaking inconveniences a
        # colleague who can be told the new address; a public one
        # breaks for readers nobody can reach, including any site that
        # has framed it.
        "published_dashboards": published.filter(is_public=False).count(),
        "public_dashboards": published.filter(is_public=True).count(),
    }


@extend_schema(tags=CONSOLE_TAG,
               summary="What a rename would break for this workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def tenant_rename_impact(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    return Response(rename_impact(tenant), status=status.HTTP_200_OK)


@extend_schema(request=TenantRenameSerializer,
               responses={200: TenantSummarySerializer}, tags=CONSOLE_TAG,
               summary="Change a workspace's address")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def rename_tenant(request, version, tenant_id):
    tenant = get_object_or_404(with_counts(console_tenants()), pk=tenant_id)
    serializer = TenantRenameSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    previous = tenant.subdomain
    tenant.subdomain = serializer.validated_data["subdomain"]
    try:
        tenant.save(update_fields=["subdomain"])
    except IntegrityError:
        # Uniqueness is the database's, as it is at registration. A
        # pre-check would only be a read before a write.
        return Response(
            {"message": "Subdomain is already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    _move_master_data(previous, tenant)
    return Response(
        TenantSummarySerializer(tenant).data, status=status.HTTP_200_OK
    )


def _move_master_data(previous, tenant):
    """Follow the device SQLite files to the new subdomain.

    Best effort, and deliberately not fatal. `download_sqlite_file`
    regenerates a missing file on the next device sync, so the worst
    case here is one slow sync and some orphaned files -- while failing
    the rename after the row has moved would leave the workspace half
    renamed, which is far worse.
    """
    new_dir = os.path.dirname(sqlite_path(Administration, tenant=tenant))
    old_dir = os.path.join(os.path.dirname(new_dir), previous)
    if not os.path.isdir(old_dir) or os.path.exists(new_dir):
        return
    try:
        os.rename(old_dir, new_dir)
    except OSError:
        logger.warning(
            "Could not move master data from %s to %s; the files will "
            "regenerate on the next device sync.", old_dir, new_dir,
        )


@extend_schema(responses={200: TenantUserSerializer(many=True)},
               tags=CONSOLE_TAG, summary="People in one workspace")
@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def tenant_users(request, version, tenant_id):
    tenant = get_object_or_404(console_tenants(), pk=tenant_id)
    users = SystemUser.objects_with_deleted.filter(
        tenant=tenant
    ).prefetch_related("mobile_assignments").order_by("email")
    return Response(
        TenantUserSerializer(users, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(responses={200: TenantUserSerializer}, tags=CONSOLE_TAG,
               summary="Deactivate a workspace user")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def deactivate_user(request, version, user_id):
    return _set_user_active(user_id, False)


@extend_schema(responses={200: TenantUserSerializer}, tags=CONSOLE_TAG,
               summary="Reactivate a workspace user")
@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def activate_user(request, version, user_id):
    return _set_user_active(user_id, True)


def _set_user_active(user_id, active):
    """Flip one workspace user's is_active.

    Scoped to accounts that belong to a workspace. An operator reached
    through here would turn "deactivate a user" into a way to lock every
    operator out of the console; they are managed on their own page.
    """
    user = get_object_or_404(
        SystemUser.objects.filter(tenant__isnull=False), pk=user_id
    )
    user.is_active = active
    user.save(update_fields=["is_active"])
    return Response(
        TenantUserSerializer(user).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: OperatorSerializer(many=True)},
               tags=CONSOLE_TAG, summary="List platform operators")
@api_view(["GET", "POST"])
@permission_classes([IsPlatformAdmin])
def operators(request, version):
    if request.method == "POST":
        return _invite_operator(request)
    queryset = SystemUser.objects.filter(
        is_platform_admin=True, tenant__isnull=True
    ).order_by("email")
    return Response(
        OperatorSerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


def _invite_operator(request):
    """Create an inactive operator and email them an activation link.

    The same two steps registration uses, for the same reason: prove
    the address, then let them set a password. Nothing here sets one.
    """
    serializer = OperatorInviteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    invited = SystemUser.objects.create(
        email=serializer.validated_data["email"],
        first_name="",
        last_name="",
        tenant=None,
        is_platform_admin=True,
        is_active=False,
    )
    invited.set_unusable_password()
    invited.save()
    send_activation_email(invited)
    return Response(
        OperatorSerializer(invited).data, status=status.HTTP_200_OK
    )


@extend_schema(responses={200: OperatorSerializer}, tags=CONSOLE_TAG,
               summary="Revoke a platform operator")
@api_view(["DELETE"])
@permission_classes([IsPlatformAdmin])
def revoke_operator(request, version, operator_id):
    """Clear the flag; keep the account.

    MT-023 adds a TenantInspection table whose operator FK is PROTECT,
    so deleting the account would raise. Clearing the flag is also what
    ends their sessions, because every console request re-checks it.
    """
    if int(operator_id) == request.user.pk:
        # The last operator revoking themselves locks everyone out, and
        # the only way back in is a shell.
        return Response(
            {"message": "You cannot revoke your own operator access"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    operator = get_object_or_404(
        SystemUser.objects.filter(
            is_platform_admin=True, tenant__isnull=True
        ),
        pk=operator_id,
    )
    operator.is_platform_admin = False
    operator.save(update_fields=["is_platform_admin"])
    return Response(
        OperatorSerializer(operator).data, status=status.HTTP_200_OK
    )
