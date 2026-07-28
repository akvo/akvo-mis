# Create your views here.
import datetime
from math import ceil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.management import call_command
from django.core.signing import BadSignature
from django.db import IntegrityError, transaction
from django.db.models import Value, Q, Count
from django.db.models.functions import Coalesce, Concat
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiParameter,
    OpenApiResponse,
)
from jsmin import jsmin
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
)
from api.v1.v1_profile.constants import FeatureAccessTypes, FeatureTypes
from api.v1.v1_users.models import (
    SystemUser,
    Organisation,
    OrganisationAttribute,
    Tenant,
)
from api.v1.v1_users.serializers import (
    LoginSerializer,
    UserSerializer,
    VerifyInviteSerializer,
    SetUserPasswordSerializer,
    ListAdministrationSerializer,
    AddEditUserSerializer,
    ListUserSerializer,
    ListUserRequestSerializer,
    ListLevelSerializer,
    UserDetailSerializer,
    ForgotPasswordSerializer,
    OrganisationListSerializer,
    AddEditOrganisationSerializer,
    OrganisationAttributeChildrenSerializer,
    RoleOptionSerializer,
    UpdateProfileSerializer,
    RegisterSerializer,
)
from mis.settings import REST_FRAMEWORK, WEBDOMAIN
from utils.custom_permissions import AddUserAccess, IsSuperAdmin
from utils.custom_serializer_fields import validate_serializers_message
from utils.default_serializers import DefaultResponseSerializer
from utils.email_helper import send_email
from utils.email_helper import ListEmailTypeRequestSerializer, EmailTypes


def send_email_to_user(type, user, request):
    url = f"{WEBDOMAIN}/login/{signing.dumps(user.pk)}"
    user = SystemUser.objects.get(pk=user.pk)
    user_forms = [
        uf.form for uf in user.user_form.all()
    ]
    listing = [
        info
        for role in user.user_user_role.all()
        for info in (
            {
                "name": "Role",
                "value": role.role.name if role.role else "N/A",
            },
            {
                "name": "Region",
                "value": role.administration.name,
            },
        )
    ]
    if user_forms:
        user_forms = ", ".join([form.name for form in user_forms])
        listing.append({"name": "Questionnaire", "value": user_forms})
    # TODO Add Administration
    data = {
        "send_to": [user.email],
        "listing": listing,
        "admin": f"""{user.name}""",
    }
    if type == EmailTypes.user_invite:
        data["button_url"] = url
    send_email(type=type, context=data)


@extend_schema(description="Use to check System health", tags=["Dev"])
@api_view(["GET"])
def health_check(request, version):
    return Response({"message": "OK"}, status=status.HTTP_200_OK)


@extend_schema(description="Get required configuration", tags=["Dev"])
@api_view(["GET"])
def get_config_file(request, version):
    if not Path("source/config/config.min.js").exists():
        call_command("generate_config")
    data = jsmin(open("source/config/config.min.js", "r").read())
    response = HttpResponse(
        data, content_type="application/x-javascript; charset=utf-8"
    )
    return response


@extend_schema(
    description="Use to show email templates",
    tags=["Dev"],
    parameters=[
        OpenApiParameter(
            name="type",
            required=False,
            enum=EmailTypes.FieldStr.keys(),
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        )
    ],
    responses={
        200: OpenApiResponse(
            description="HTML email template",
            response=OpenApiTypes.STR
        )
    },
    summary="To show email template by type",
)
@api_view(["GET"])
def email_template(request, version):
    serializer = ListEmailTypeRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    email_type = serializer.validated_data.get("type")
    data = {"subject": "Test", "send_to": []}
    email = send_email(type=email_type, context=data, send=False)
    return HttpResponse(email)


def authenticated_response(user):
    # Signing in and signing up hand back the same thing: a fresh access
    # token, the serialized user, and the cookie the SPA reads. Kept in
    # one place so the two entry points cannot drift apart.
    user.last_login = timezone.now()
    user.save()
    refresh = RefreshToken.for_user(user)
    expiration_time = timezone.make_aware(
        datetime.datetime.fromtimestamp(refresh.access_token["exp"])
    )
    data = UserSerializer(instance=user).data
    data["token"] = str(refresh.access_token)
    data["invite"] = signing.dumps(user.pk)
    data["expiration_time"] = expiration_time
    response = Response(data, status=status.HTTP_200_OK)
    response.set_cookie(
        "AUTH_TOKEN", str(refresh.access_token), expires=expiration_time
    )
    return response


# TODO: Remove temp user entry and invite key from the response.
@extend_schema(
    request=LoginSerializer,
    responses={200: UserSerializer, 401: DefaultResponseSerializer},
    tags=["Auth"],
)
@api_view(["POST"])
def login(request, version):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Legacy convenience account, now test-only: dozens of test modules
    # log in as admin@akvo.org without seeding it first. Production
    # never auto-creates credentials — registration is the way in.
    if settings.TESTING and not SystemUser.objects.all().count():
        SystemUser.objects.create_superuser(
            email="admin@akvo.org",
            password="Test105*",
            first_name="Admin",
            last_name="MIS",
        )

    user = authenticate(
        email=serializer.validated_data["email"],
        password=serializer.validated_data["password"],
    )

    if user:
        if user.deleted_at:
            return Response(
                {"message": "User has been deleted"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return authenticated_response(user)
    return Response(
        {"message": "Invalid login credentials"},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@extend_schema(
    request=RegisterSerializer,
    responses={200: UserSerializer, 400: DefaultResponseSerializer},
    tags=["Auth"],
)
@api_view(["POST"])
def register(request, version):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "message": validate_serializers_message(serializer.errors),
                "details": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    validated = serializer.validated_data
    # Free-tier sign-up: the registrant becomes a superadmin of their own
    # tenant. Everything is one transaction so a partial tenant (user
    # without hierarchy, tenant without user) is unreachable.
    try:
        with transaction.atomic():
            tenant = Tenant.objects.create(subdomain=validated["subdomain"])
            user = SystemUser.objects.create_superuser(
                email=validated["email"],
                password=validated["password"],
                first_name=validated["first_name"],
                last_name=validated["last_name"],
                tenant=tenant,
            )
            # A registrant needs a resolvable profile: superuser scoping
            # substitutes the tenant's root administration. Every tenant
            # gets its own level 0 and root unit — hierarchies are
            # disjoint from birth, even though queries are not yet
            # tenant-filtered.
            level_zero = Levels.objects.create(
                name="", level=0, tenant=tenant
            )
            Administration.objects.create(
                parent=None,
                level=level_zero,
                name=validated["subdomain"],
                tenant=tenant,
            )
    except IntegrityError:
        # Uniqueness is enforced once, by the database. A pre-check in the
        # serializer would only be a read before a write — two concurrent
        # sign-ups would both pass it and one would still lose here. The
        # rolled-back transaction lets us name the field that lost.
        taken = (
            "Email"
            if SystemUser.objects.filter(email=validated["email"]).exists()
            else "Subdomain"
        )
        return Response(
            {"message": f"{taken} is already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Same payload as login, so the frontend reuses the login success path.
    return authenticated_response(user)


@extend_schema(
    responses={200: UserSerializer},
    tags=["Auth"],
    summary="Get user details from token",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request, version):
    # check user activity
    user = SystemUser.objects.filter(
        email=request.user, deleted_at=None
    ).first()
    if not user:
        return Response(
            {"message": "User has been deleted"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    # calculate last activity
    now = timezone.now()
    last_active = user.last_login
    time_diff_hours = None
    if last_active:
        time_diff = now - last_active
        time_diff_hours = time_diff.total_seconds() / 3600
    if time_diff_hours and time_diff_hours >= 4:
        # revoke/logout after 4 hours inactivity
        return Response(
            {"message": "Expired of 4 hours inactivity"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response(
        UserSerializer(instance=request.user).data, status=status.HTTP_200_OK
    )


@extend_schema(
    request=VerifyInviteSerializer,
    responses={200: DefaultResponseSerializer, 400: DefaultResponseSerializer},
    tags=["User"],
    summary="To verify invitation code",
)
@api_view(["GET"])
def verify_invite(request, version, invitation_id):
    try:
        pk = signing.loads(invitation_id)
        user = SystemUser.objects.get(pk=pk, deleted_at=None)
        return Response(
            {"name": user.get_full_name()}, status=status.HTTP_200_OK
        )
    except BadSignature:
        return Response(
            {"message": "Invalid invite code"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except SystemUser.DoesNotExist:
        return Response(
            {"message": "Invalid invite code"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@extend_schema(
    request=SetUserPasswordSerializer,
    responses={200: UserSerializer},
    tags=["User"],
    summary="To set user's password",
)
@api_view(["PUT"])
def set_user_password(request, version):
    serializer = SetUserPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user: SystemUser = serializer.validated_data.get("invite")
    user.set_password(serializer.validated_data.get("password"))
    user.updated = timezone.now()
    user.save()
    refresh = RefreshToken.for_user(user)
    data = UserSerializer(instance=user).data
    data["token"] = str(refresh.access_token)
    # TODO: remove invite from response
    data["invite"] = signing.dumps(user.pk)
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: ListAdministrationSerializer},
    tags=["Administration"],
    parameters=[
        OpenApiParameter(
            name="filter",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="filter_children",
            required=False,
            type={"type": "array", "items": {"type": "number"}},
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="max_level",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
    ],
    summary="Get list of administration",
)
@api_view(["GET"])
def list_administration(request, version, administration_id):
    instance = get_object_or_404(
        Administration.objects.for_user(request.user), pk=administration_id
    )
    filter = request.GET.get("filter")
    max_level = request.GET.get("max_level")
    filter_children = request.GET.getlist("filter_children")
    return Response(
        ListAdministrationSerializer(
            instance=instance,
            context={
                "filter": filter,
                "max_level": max_level,
                "filter_children": filter_children,
            },
        ).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    responses={200: ListLevelSerializer(many=True)},
    tags=["Administration"],
    summary="Get list of levels",
)
@api_view(["GET"])
def list_levels(request, version):
    response = Response(
        ListLevelSerializer(
            instance=Levels.objects.for_user(request.user), many=True
        ).data,
        status=status.HTTP_200_OK,
    )
    # Levels are per-tenant and fetched at runtime now, so a cached copy
    # would follow one tenant's tiers into another's session.
    response["Cache-Control"] = "no-cache"
    return response


@extend_schema(
    request=AddEditUserSerializer,
    responses={200: DefaultResponseSerializer},
    tags=["User"],
    description="Role Choice are SuperAdmin:1,Admin:2",
    summary="To add user",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, AddUserAccess])
def add_user(request, version):
    serializer = AddEditUserSerializer(
        data=request.data, context={"user": request.user}
    )
    try:
        if not serializer.is_valid():
            return Response(
                {
                    "message": validate_serializers_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        # Handle unexpected validation errors
        error_message = str(e)
        if hasattr(e, 'detail'):
            return Response(
                {
                    "message": validate_serializers_message(e.detail),
                    "details": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "message": error_message,
                "details": {"error": error_message}
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.save()

    if serializer.validated_data.get("inform_user"):
        send_email_to_user(
            type=EmailTypes.user_invite, user=user, request=request
        )
    return Response(
        {"message": "User added successfully"},
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    responses={
        (200, "application/json"): inline_serializer(
            "UserList",
            fields={
                "current": serializers.IntegerField(),
                "total": serializers.IntegerField(),
                "total_page": serializers.IntegerField(),
                "data": ListUserSerializer(many=True),
            },
        )
    },
    tags=["User"],
    summary="Get list of users",
    parameters=[
        OpenApiParameter(
            name="page",
            required=True,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="trained",
            required=False,
            default=None,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="role",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="organisation",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="administration",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="pending",
            required=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="search",
            required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, AddUserAccess])
def list_users(request, version):
    serializer = ListUserRequestSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    filter_data = {}
    exclude_data = {"password__exact": ""}

    if not request.user.is_superuser:
        filter_data["is_superuser"] = False

    filter_adm = serializer.validated_data.get("administration")
    if not request.user.is_superuser:
        user_adm_queryset = request.user.user_user_role.filter(
            role__role_role_feature_access__type=FeatureTypes.user_access,
            role__role_role_feature_access__access=(
                FeatureAccessTypes.invite_user
            ),
        ).order_by(
            "administration__level__level"
        )
        if not filter_adm and user_adm_queryset.exists():
            # Handle multiple user roles - collect accessible administrations
            all_accessible_adm_ids = set()
            for user_role in user_adm_queryset:
                adm = user_role.administration
                # Add the administration itself
                all_accessible_adm_ids.add(adm.id)
                # Add all descendants of this administration
                filter_path = "{0}{1}.".format(
                    adm.path, adm.id
                ) if adm.path else f"{adm.id}."
                descendants = Administration.objects.filter(
                    path__startswith=filter_path
                ).values_list("id", flat=True)
                all_accessible_adm_ids.update(descendants)

            # Apply filter by all accessible administration IDs
            filter_data["user_user_role__administration_id__in"] = list(
                all_accessible_adm_ids
            )
        elif filter_adm:
            # Handle single administration filter (when explicitly specified)
            filter_path = "{0}{1}.".format(
                filter_adm.path, filter_adm.id
            ) if filter_adm.path else f"{filter_adm.id}."
            filter_descendants = list(
                Administration.objects.filter(
                    path__startswith=filter_path
                ).values_list("id", flat=True)
            )
            filter_descendants.append(filter_adm.id)
            final_set = set(filter_descendants)

            # Apply filter by administration IDs
            # Only apply filtering if administration level > 0 (not national)
            if filter_adm.level.level > 0:
                filter_data["user_user_role__administration_id__in"] = list(
                    final_set
                )
    if serializer.validated_data.get("trained") is not None:
        trained = (
            True
            if serializer.validated_data.get("trained").lower() == "true"
            else False
        )
        filter_data["trained"] = trained
    if serializer.validated_data.get("role"):
        role = serializer.validated_data.get("role")
        # Use direct filter on role object instead of role_id
        filter_data["user_user_role__role"] = role
    if serializer.validated_data.get("organisation"):
        filter_data["organisation_id"] = serializer.validated_data.get(
            "organisation"
        )
    if serializer.validated_data.get("pending"):
        filter_data["password__exact"] = ""
        exclude_data.pop("password__exact")

    page_size = REST_FRAMEWORK.get("PAGE_SIZE")
    the_past = timezone.now() - datetime.timedelta(days=10 * 365)
    # also filter soft deletes
    queryset = SystemUser.objects.for_user(request.user).filter(
        deleted_at=None, **filter_data
    )
    # filter by email or fullname
    if serializer.validated_data.get("search"):
        search = serializer.validated_data.get("search")
        queryset = queryset.annotate(
            fullname=Concat("first_name", Value(" "), "last_name")
        )
        queryset = queryset.filter(
            Q(email__icontains=search) | Q(fullname__icontains=search)
        )
    # First get unique IDs to avoid duplicates from joins
    # But make sure to include current user's ID
    user_ids = list(queryset.exclude(**exclude_data)
                    .values_list('id', flat=True)
                    .distinct())

    # Then query again with the distinct IDs
    queryset = (
        SystemUser.objects.filter(id__in=user_ids)
        .annotate(last_updated=Coalesce("updated", Value(the_past)))
        .order_by("-last_updated", "-date_joined")
    )
    paginator = PageNumberPagination()
    instance = paginator.paginate_queryset(queryset, request)
    data = {
        "current": request.GET.get("page"),
        "data": ListUserSerializer(instance=instance, many=True).data,
        "total": queryset.count(),
        "total_page": ceil(queryset.count() / page_size),
    }
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: RoleOptionSerializer(many=True)},
    tags=["User"],
    summary="Get list of roles",
)
@api_view(["GET"])
def get_user_roles(request, version):
    roles = Role.objects.order_by("administration_level__level").all()
    data = RoleOptionSerializer(
        instance=roles,
        many=True,
        context={"request": request},
    ).data
    return Response(data, status=status.HTTP_200_OK)


class UserEditDeleteView(APIView):
    permission_classes = [IsAuthenticated, AddUserAccess]

    @extend_schema(
        responses={200: UserDetailSerializer, 204: DefaultResponseSerializer},
        tags=["User"],
        summary="To get user details",
    )
    def get(self, request, user_id, version):
        instance = get_object_or_404(
            SystemUser.objects.for_user(request.user),
            pk=user_id,
            deleted_at=None,
        )
        return Response(
            UserDetailSerializer(
                instance=instance,
                context={"user": request.user}
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["User"],
        summary="To delete user",
    )
    def delete(self, request, user_id, version):
        login_user = SystemUser.objects.get(email=request.user)
        instance = get_object_or_404(
            SystemUser.objects.for_user(request.user), pk=user_id
        )
        # prevent self deletion
        if login_user.id == instance.id:
            return Response(
                {"message": "Could not do self deletion"},
                status=status.HTTP_409_CONFLICT,
            )
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=AddEditUserSerializer,
        responses={200: DefaultResponseSerializer},
        tags=["User"],
        description="Role Choice are SuperAdmin:1,Admin:2,User:4",
        summary="To update user",
    )
    def put(self, request, user_id, version):
        instance = get_object_or_404(
            SystemUser.objects.for_user(request.user),
            pk=user_id,
            deleted_at=None,
        )
        serializer = AddEditUserSerializer(
            data=request.data,
            context={"user": request.user},
            instance=instance,
        )
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()

        # inform user by inform_user payload
        if serializer.validated_data.get("inform_user"):
            send_email_to_user(
                type=EmailTypes.user_update, user=user, request=request
            )
        return Response(
            {"message": "User updated successfully"}, status=status.HTTP_200_OK
        )


@extend_schema(
    request=ForgotPasswordSerializer,
    responses={200: DefaultResponseSerializer},
    tags=["User"],
    summary="To send reset password instructions",
)
@api_view(["POST"])
def forgot_password(request, version):
    serializer = ForgotPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user: SystemUser = serializer.validated_data.get("email")
    url = f"{WEBDOMAIN}/login/{signing.dumps(user.pk)}"
    data = {"button_url": url, "send_to": [user.email]}
    send_email(type=EmailTypes.user_forgot_password, context=data)
    return Response(
        {"message": "Reset password instructions sent to your email"},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    responses={200: OrganisationListSerializer(many=True)},
    parameters=[
        OpenApiParameter(
            name="attributes",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="id",
            required=False,
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="search",
            required=False,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
    tags=["Organisation"],
    summary="Get list of organisation",
)
@api_view(["GET"])
def list_organisations(request, version):
    id = request.GET.get("id")
    attributes = request.GET.get("attributes")
    search = request.GET.get("search")

    instance = Organisation.objects.for_user(request.user).prefetch_related(
        'organisation_organisation_attribute'
    ).annotate(user_count=Count('user_organisation')).all()

    if id:
        instance = instance.filter(pk=id)
    if attributes and not id:
        ids = OrganisationAttribute.objects.filter(type=attributes).distinct(
            "organisation_id"
        )
        instance = instance.filter(
            pk__in=[o.organisation_id for o in ids]
        )
    if search and not id:
        instance = instance.filter(name__icontains=search)

    return Response(
        OrganisationListSerializer(instance=instance, many=True).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=AddEditOrganisationSerializer,
    responses={200: DefaultResponseSerializer},
    tags=["Organisation"],
    description="Attributes are member:1,partnership:2",
    summary="To add new organisation",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def add_organisation(request, version):
    serializer = AddEditOrganisationSerializer(
        data=request.data,
        context={"attributes": request.data.get("attributes")},
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer.save()
    return Response(
        {"message": "Organisation added successfully"},
        status=status.HTTP_200_OK,
    )


class OrganisationEditDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        responses={200: OrganisationListSerializer},
        tags=["Organisation"],
        summary="To get organisation details",
    )
    def get(self, request, organisation_id, version):
        instance = get_object_or_404(
            Organisation.objects.for_user(request.user).annotate(
                user_count=Count('user_organisation')
            ),
            pk=organisation_id
        )
        return Response(
            OrganisationListSerializer(instance=instance).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deletion with no response")
        },
        tags=["Organisation"],
        summary="To delete organisation",
    )
    def delete(self, request, organisation_id, version):
        instance = get_object_or_404(
            Organisation.objects.for_user(request.user), pk=organisation_id
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=AddEditOrganisationSerializer,
        responses={
            200: DefaultResponseSerializer,
            400: DefaultResponseSerializer,
        },
        tags=["Organisation"],
        description="Attributes are member:1,partnership:2",
        summary="To update organisation",
    )
    def put(self, request, organisation_id, version):
        instance = get_object_or_404(
            Organisation.objects.for_user(request.user), pk=organisation_id
        )
        serializer = AddEditOrganisationSerializer(
            data=request.data,
            context={"attributes": request.data.get("attributes")},
            instance=instance,
        )
        if not serializer.is_valid():
            return Response(
                {"message": validate_serializers_message(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(
            {"message": "Organisation updated successfully"},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    responses={200: OrganisationAttributeChildrenSerializer},
    parameters=[
        OpenApiParameter(
            name="attribute",
            required=True,
            enum=OrganisationTypes.FieldStr.keys(),
            type=OpenApiTypes.NUMBER,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="selected_id",
            required=False,
            location=OpenApiParameter.PATH,
            type=OpenApiTypes.NUMBER,
            description="ID of the selected organization (optional)",
        ),
    ],
    tags=["Organisation"],
    summary="Get list of organisations for webform options",
)
@api_view(["GET"])
def list_organisation_options(request, version, selected_id=None):
    attribute = request.GET.get("attribute")
    if selected_id:
        return Response(
            {"type_id": attribute, "name": selected_id, "children": []},
            status=status.HTTP_200_OK,
        )
    instance = None
    if attribute:
        instance = OrganisationAttribute.objects.filter(type=attribute).first()
    return Response(
        OrganisationAttributeChildrenSerializer(instance=instance).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=UpdateProfileSerializer,
    responses={200: UserSerializer},
    tags=["User"],
    summary="To update user profile",
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_profile(request, version):
    serializer = UpdateProfileSerializer(
        data=request.data, instance=request.user
    )
    if not serializer.is_valid():
        return Response(
            {"message": validate_serializers_message(serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = serializer.save()
    return Response(
        UserSerializer(instance=user).data,
        status=status.HTTP_200_OK
    )
