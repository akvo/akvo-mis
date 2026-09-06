from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from django.core import signing
from django.core.signing import BadSignature
from django.utils import timezone
from django.db.models import Q, Min
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

# from api.v1.v1_approval.constants import DataApprovalStatus
from api.v1.v1_forms.models import (
    UserForms,
    Forms,
)
from api.v1.v1_forms.constants import FormStatus
from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_profile.models import (
    Administration,
    Levels,
    Role,
    UserRole,
)
from api.v1.v1_users.models import (
    SystemUser,
    Organisation,
    OrganisationAttribute,
)
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_approval.models import DataBatch
from utils.custom_serializer_fields import (
    TenantScopedPrimaryKeyRelatedField,
    CustomEmailField,
    CustomCharField,
    CustomPrimaryKeyRelatedField,
    CustomBooleanField,
    CustomMultipleChoiceField,
)
from api.v1.v1_profile.constants import FeatureAccessTypes
from django.conf import settings
from utils.custom_helper import CustomPasscode
from utils.custom_generator import update_sqlite
from utils.tenant_host import embed_hostname
from utils.tenant_scoped_model import TenantStampedSerializerMixin, acting_user


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name"]


class OrganisationAttributeSerializer(serializers.ModelSerializer):
    type_id = serializers.ReadOnlyField(source="type")
    name = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance: OrganisationAttribute):
        return OrganisationTypes.FieldStr.get(instance.type)

    class Meta:
        model = OrganisationAttribute
        fields = ["type_id", "name"]


class OrganisationAttributeChildrenSerializer(serializers.ModelSerializer):
    type_id = serializers.ReadOnlyField(source="type")
    name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance: OrganisationAttribute):
        return OrganisationTypes.FieldStr.get(instance.type)

    @extend_schema_field(OrganisationSerializer(many=True))
    def get_children(self, instance: OrganisationAttribute):
        orgs = Organisation.objects.filter(
            organisation_organisation_attribute__type=instance.type
        ).all()
        return OrganisationSerializer(instance=orgs, many=True).data

    class Meta:
        model = OrganisationAttribute
        fields = ["type_id", "name", "children"]


class OrganisationListSerializer(serializers.ModelSerializer):
    attributes = serializers.SerializerMethodField()
    users = serializers.IntegerField(source="user_count")

    @extend_schema_field(OrganisationAttributeSerializer(many=True))
    def get_attributes(self, instance: Organisation):
        # Use the prefetched data instead of querying the database again
        attr = instance.organisation_organisation_attribute.all()
        return OrganisationAttributeSerializer(instance=attr, many=True).data

    class Meta:
        model = Organisation
        fields = ["id", "name", "attributes", "users"]


class AddEditOrganisationSerializer(
    TenantStampedSerializerMixin, serializers.ModelSerializer
):
    attributes = CustomMultipleChoiceField(
        choices=list(OrganisationTypes.FieldStr.keys()), required=True
    )

    def create(self, validated_data):
        attributes = validated_data.pop("attributes")
        instance = super(AddEditOrganisationSerializer, self).create(
            validated_data
        )
        for attr in attributes:
            OrganisationAttribute.objects.create(
                organisation=instance, type=attr
            )
        update_sqlite(
            model=Organisation,
            data={
                "id": instance.id,
                "name": instance.name,
            },
            tenant=instance.tenant,
        )
        return instance

    def update(self, instance, validated_data):
        attributes = validated_data.pop("attributes")
        instance: Organisation = super(
            AddEditOrganisationSerializer, self
        ).update(instance, validated_data)
        instance.save()
        current_attributes = OrganisationAttribute.objects.filter(
            organisation=instance
        ).all()
        for attr in current_attributes:
            if attr.type not in attributes:
                attr.delete()
        for attr in attributes:
            attr, created = OrganisationAttribute.objects.get_or_create(
                organisation=instance, type=attr
            )
            attr.save()
        update_sqlite(
            model=Organisation,
            data={"name": instance.name},
            tenant=instance.tenant,
            id=instance.id,
        )
        return instance

    class Meta:
        model = Organisation
        fields = ["name", "attributes"]


class LoginSerializer(serializers.Serializer):
    email = CustomEmailField()
    password = CustomCharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = CustomEmailField()

    def validate_email(self, email):
        tenant = self.context.get("tenant")
        qs = SystemUser.objects.filter(email=email, deleted_at=None)
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        user = qs.first()
        if not user:
            raise ValidationError("Invalid email, user not found")
        return user


class VerifyInviteSerializer(serializers.Serializer):
    invite = CustomCharField()

    def validate_invite(self, invite):
        try:
            pk = signing.loads(invite)
            user = SystemUser.objects.get(pk=pk)
        except BadSignature:
            raise ValidationError("Invalid invite code")
        except SystemUser.DoesNotExist:
            raise ValidationError("Invalid invite code")
        return user


class SetUserPasswordSerializer(serializers.Serializer):
    password = CustomCharField()
    confirm_password = CustomCharField()
    invite = CustomCharField()

    def validate_invite(self, invite):
        try:
            pk = signing.loads(invite)
            user = SystemUser.objects.get(pk=pk, deleted_at=None)
        except BadSignature:
            raise ValidationError("Invalid invite code")
        except SystemUser.DoesNotExist:
            raise ValidationError("Invalid invite code")
        return user

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise ValidationError(
                {
                    "confirm_password": "Confirm password and password"
                    " are not same"
                }
            )
        return attrs


class ListAdministrationChildrenSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, instance: Administration):
        return instance.full_path_name

    class Meta:
        model = Administration
        fields = ["id", "parent", "path", "level", "name", "full_name"]


class ListAdministrationSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    level_name = serializers.ReadOnlyField(source="level.name")
    level = serializers.ReadOnlyField(source="level.level")
    children_level_name = serializers.SerializerMethodField()

    @extend_schema_field(ListAdministrationChildrenSerializer(many=True))
    def get_children(self, instance: Administration):
        max_level = self.context.get("max_level")
        filter_children = self.context.get("filter_children")
        if max_level:
            if int(max_level) <= instance.level.level:
                return []
        filter = self.context.get("filter")
        if filter:
            filtered_administration = (
                Administration.objects.filter(id=filter).all().order_by("name")
            )
            return ListAdministrationChildrenSerializer(
                filtered_administration, many=True
            ).data
        children = instance.parent_administration.all().order_by("name")
        if len(filter_children):
            children = (
                instance.parent_administration.filter(pk__in=filter_children)
                .all()
                .order_by("name")
            )
        return ListAdministrationChildrenSerializer(
            instance=children, many=True
        ).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_children_level_name(self, instance: Administration):
        child: Administration = instance.parent_administration.first()
        if child:
            return child.level.name
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, instance: Administration):
        return instance.full_path_name

    class Meta:
        model = Administration
        fields = [
            "id",
            "full_name",
            "path",
            "parent",
            "name",
            "level_name",
            "level",
            "children",
            "children_level_name",
        ]


class AddRolesSerializer(serializers.Serializer):
    role = TenantScopedPrimaryKeyRelatedField(
        queryset=Role.objects.none(),
        required=True,
        help_text="Role to assign to user",
    )
    administration = TenantScopedPrimaryKeyRelatedField(
        queryset=Administration.objects.none(),
        required=True,
        help_text="Administration to assign role to user",
    )

    def validate_administration(self, administration):
        user = self.context.get("user")
        if user.is_superuser:
            return administration
        if not user:
            raise ValidationError(
                "User context is required for role validation"
            )
        invite_u = FeatureAccessTypes.invite_user
        user_role = user.user_user_role.filter(
            role__role_role_feature_access__access=invite_u,
        ).first()
        if not user_role:
            raise ValidationError("You do not have permission to assign roles")
        user_adm_level = user_role.administration.level.level
        if user_adm_level > administration.level.level:
            raise ValidationError(
                "You do not have permission to add users at "
                "a higher administration level"
            )
        # Check if the administration is outside the user's administration path
        user_adm_paths = [
            f"{ur.administration.path}{ur.administration.id}."
            for ur in user.user_user_role.all()
        ]
        invalid_children = (
            administration.level.level > user_adm_level
            and not any(
                administration.path.startswith(path) for path in user_adm_paths
            )
        )
        invalid_adm = (
            administration.level.level == user_adm_level
            and administration.id
            not in user.user_user_role.values_list(
                "administration__id", flat=True
            )
        )
        if invalid_children or invalid_adm:
            raise ValidationError(
                "You do not have permission to add users "
                "in this administration"
            )
        return administration

    def validate_role(self, role):
        user = self.context.get("user")
        if user.is_superuser:
            return role
        if not user:
            raise ValidationError(
                "User context is required for role validation"
            )
        invite_u = FeatureAccessTypes.invite_user
        user_role = user.user_user_role.filter(
            role__role_role_feature_access__access=invite_u,
        ).first()
        if not user_role:
            raise ValidationError("You do not have permission to assign roles")
        user_adm_level = user_role.administration.level.level
        if user_adm_level > role.administration_level.level:
            raise ValidationError(
                "You do not have permission to add users "
                "with this role's administration level"
            )
        return role

    def validate(self, attrs):
        role = attrs.get("role")
        administration = attrs.get("administration")
        # check adm level mismatch between role and administration
        if role.administration_level.level != administration.level.level:
            raise ValidationError("Role and administration level mismatch")
        return attrs

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("role").queryset = Role.objects.all()
        admin_field = self.fields.get("administration")
        admin_field.queryset = Administration.objects.all()

    class Meta:
        fields = ["role", "administration"]


class AddEditUserSerializer(
    TenantStampedSerializerMixin, serializers.ModelSerializer
):
    organisation = TenantScopedPrimaryKeyRelatedField(
        queryset=Organisation.objects.none(), required=False
    )
    trained = CustomBooleanField(default=False)
    roles = AddRolesSerializer(many=True, required=False)
    forms = CustomPrimaryKeyRelatedField(
        queryset=Forms.objects.filter(
            parent__isnull=True,
        ).all(),
        many=True,
        required=False,
    )
    inform_user = CustomBooleanField(default=True)
    is_superuser = CustomBooleanField(
        default=False,
        required=False,
        help_text="Set user as superuser. Superuser can access all data.",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("organisation").queryset = Organisation.objects.all()

    def validate_roles(self, roles):
        return AddRolesSerializer(
            data=roles, many=True, context=self.context
        ).is_valid(raise_exception=True)

    def validate_email(self, value):
        acting = acting_user(self.context)
        acting_tenant_id = getattr(acting, "tenant_id", None)

        existing = SystemUser.objects_with_deleted.filter(
            email=value,
            tenant_id=acting_tenant_id,
        ).first()

        if existing is None:
            return value

        if self.instance and self.instance.pk == existing.pk:
            return value

        if existing.deleted_at is not None:
            # Soft-deleted in same tenant — create() restore path handles it.
            return value

        raise serializers.ValidationError(
            "This email is already in your workspace. "
            "To make changes, edit the existing user."
        )

    def create(self, validated_data):
        acting = acting_user(self.context)
        user_deleted = (
            SystemUser.objects_deleted.for_user(acting)
            .filter(email=validated_data["email"])
            .first()
        )
        if user_deleted:
            user_deleted.restore()
            self.update(instance=user_deleted, validated_data=validated_data)
            return user_deleted

        # delete inform_user payload
        validated_data.pop("inform_user", None)
        roles_data = validated_data.pop("roles", [])
        forms = validated_data.pop("forms", [])
        user = super(AddEditUserSerializer, self).create(validated_data)
        # Assign roles to user
        if roles_data:
            for role_data in roles_data:
                UserRole.objects.create(
                    user=user,
                    administration=role_data["administration"],
                    role=role_data["role"],
                )
        # add new user forms
        for form in forms:
            UserForms.objects.create(user=user, form=form)
        # if forms is empty and is_superuser is True
        # then assign all published forms to user
        if not forms and user.is_superuser:
            published_forms = Forms.objects.filter(
                status=FormStatus.published
            ).all()
            for form in published_forms:
                UserForms.objects.create(user=user, form=form)
        return user

    def update(self, instance, validated_data):
        # delete inform_user payload
        validated_data.pop("inform_user", None)
        # pop roles request data
        roles_data = validated_data.pop("roles", None)
        # pop forms request data
        forms = validated_data.pop("forms", None)
        instance: SystemUser = super(AddEditUserSerializer, self).update(
            instance, validated_data
        )
        instance.updated = timezone.now()
        instance.save()

        if forms:
            # Delete old user forms
            user_forms = UserForms.objects.filter(user=instance).all()
            user_forms.delete()
            for form in forms:
                UserForms.objects.create(user=instance, form=form)
        # Handle multiple role assignments
        if roles_data:
            # Get existing roles
            existing_roles = UserRole.objects.filter(user=instance).all()
            # Create a set of unique identifiers for existing roles
            existing_role_identifiers = {
                (str(role.role.id), str(role.administration.id)): role
                for role in existing_roles
            }

            # Create a set of unique identifiers for new roles
            new_role_identifiers = {}
            for role_data in roles_data:
                role_id = str(role_data["role"].id)
                admin_id = str(role_data["administration"].id)
                new_role_identifiers[(role_id, admin_id)] = role_data
            # Delete roles that are not in the new set
            for key, role in list(existing_role_identifiers.items()):
                if key not in new_role_identifiers:
                    role.delete()
            # Create or update roles
            for key, role_data in new_role_identifiers.items():
                if key in existing_role_identifiers:
                    # Update existing role
                    role = existing_role_identifiers[key]
                    role.role = role_data["role"]
                    role.administration = role_data["administration"]
                    role.save()
                else:
                    # Create new role
                    UserRole.objects.create(
                        user=instance,
                        administration=role_data["administration"],
                        role=role_data["role"],
                    )
        else:
            # If no roles provided, delete all roles
            UserRole.objects.filter(user=instance).delete()
        return instance

    def to_internal_value(self, data):
        roles_data = data.pop("roles", None)
        internal_value = super().to_internal_value(data)

        if roles_data:
            # Validate each role data
            serializer = AddRolesSerializer(
                data=roles_data, many=True, context=self.context
            )
            if not serializer.is_valid():
                errors = {}
                # Process role validation errors
                if any("role" in item for item in serializer.errors):
                    role_errors = []
                    for i, error_item in enumerate(serializer.errors):
                        if "role" in error_item:
                            for err in error_item["role"]:
                                if "does not exist" in str(err):
                                    try:
                                        invalid_id = str(roles_data[i]["role"])
                                        role_errors.append(
                                            f"Invalid role ID: {invalid_id}"
                                        )
                                    except (IndexError, KeyError):
                                        role_errors.append("Invalid role ID")
                                else:
                                    role_errors.append(str(err))
                    if role_errors:
                        errors["role"] = role_errors

                # Process administration validation errors
                if any("administration" in item for item in serializer.errors):
                    admin_errors = []
                    for i, error_item in enumerate(serializer.errors):
                        if "administration" in error_item:
                            for err in error_item["administration"]:
                                if "does not exist" in str(err):
                                    try:
                                        invalid_id = str(
                                            roles_data[i]["administration"]
                                        )
                                        admin_errors.append(
                                            f"Invalid administration ID: "
                                            f"{invalid_id}"
                                        )
                                    except (IndexError, KeyError):
                                        admin_errors.append(
                                            "Invalid administration ID"
                                        )
                                else:
                                    admin_errors.append(str(err))
                    if admin_errors:
                        errors["administration"] = admin_errors
                # Raise custom ValidationError with better error messages
                if errors:
                    raise ValidationError(errors)
                # Otherwise, re-raise the original errors
                raise ValidationError(serializer.errors)
            internal_value["roles"] = serializer.validated_data

        return internal_value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Get user roles
        user_roles = UserRole.objects.filter(user=instance).all()

        # Convert roles to representation
        roles_data = []
        for role in user_roles:
            roles_data.append(
                {
                    "role": role.role.id,
                    "administration": role.administration.id,
                }
            )

        representation["roles"] = roles_data
        return representation

    class Meta:
        model = SystemUser
        fields = [
            "first_name",
            "last_name",
            "email",
            "organisation",
            "trained",
            "roles",
            "phone_number",
            "forms",
            "inform_user",
            "is_superuser",
        ]
        extra_kwargs = {
            "email": {"validators": []},
        }


class UserAdministrationSerializer(serializers.ModelSerializer):
    level = serializers.ReadOnlyField(source="level.level")
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, instance: Administration):
        return instance.full_name

    class Meta:
        model = Administration
        fields = ["id", "name", "level", "level_id", "full_name"]


class UserFormSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="form.id")
    name = serializers.ReadOnlyField(source="form.name")

    class Meta:
        model = UserForms
        fields = ["id", "name"]


class UserRoleSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role.name")
    administration = serializers.CharField(source="administration.full_name")

    class Meta:
        model = UserRole
        fields = [
            "role",
            "administration",
        ]


class ListUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()
    trained = CustomBooleanField()
    invite = serializers.SerializerMethodField()
    forms = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()

    @extend_schema_field(UserRoleSerializer(many=True))
    def get_roles(self, instance: SystemUser):
        return UserRoleSerializer(
            instance=instance.user_user_role.all(),
            many=True,
        ).data

    @extend_schema_field(OrganisationSerializer)
    def get_organisation(self, instance: SystemUser):
        return OrganisationSerializer(instance=instance.organisation).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_invite(self, instance: SystemUser):
        return signing.dumps(instance.id)

    @extend_schema_field(UserFormSerializer(many=True))
    def get_forms(self, instance: SystemUser):
        return UserFormSerializer(
            instance=instance.user_form.all(), many=True
        ).data

    @extend_schema_field(OpenApiTypes.INT)
    def get_last_login(self, instance):
        if instance.last_login:
            return instance.last_login.timestamp()
        return None

    class Meta:
        model = SystemUser
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "roles",
            "organisation",
            "trained",
            "phone_number",
            "invite",
            "forms",
            "last_login",
        ]


class ListUserRequestSerializer(serializers.Serializer):
    trained = CustomCharField(required=False, default=None)
    organisation = CustomPrimaryKeyRelatedField(
        queryset=Organisation.objects.none(), required=False
    )
    administration = CustomPrimaryKeyRelatedField(
        queryset=Administration.objects.none(), required=False
    )
    role = CustomPrimaryKeyRelatedField(
        queryset=Role.objects.none(), required=False
    )
    pending = CustomBooleanField(default=False)
    descendants = CustomBooleanField(default=True)
    search = CustomCharField(required=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("administration").queryset = (
            Administration.objects.all()
        )
        self.fields.get("organisation").queryset = Organisation.objects.all()
        self.fields.get("role").queryset = Role.objects.all()


class UserRoleListSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role.name")
    administration = serializers.SerializerMethodField()

    @extend_schema_field(UserAdministrationSerializer)
    def get_administration(self, instance: UserRole):
        if instance.administration:
            return UserAdministrationSerializer(
                instance=instance.administration
            ).data
        return None

    class Meta:
        model = UserRole
        fields = [
            "id",
            "role",
            "administration",
            "is_approver",
            "is_submitter",
            "is_editor",
            "can_delete",
            "can_invite_user",
            "can_form_builder",
            "can_form_delete",
            "can_form_create",
            "can_form_edit",
            "can_form_publish",
            "can_dashboard_view",
            "can_dashboard_create",
            "can_dashboard_edit",
            "can_dashboard_publish",
            "can_dashboard_delete",
        ]


def tenant_is_configured(tenant):
    """Has this tenant completed the configuration form?

    Derived rather than stored: a configured tenant is one with a *named*
    level 0 and a root unit, which is exactly what the form creates. The
    same predicate the bulk-upload gate will reuse, so there is no column
    to keep in step with reality.

    A tenant-less user — createsuperuser, the test-only admin account —
    reads as configured. There is nothing for them to configure, and
    answering False would strand them on the configuration form and let
    them create a tenant-less level 0 in the legacy global hierarchy.
    """
    if not tenant:
        return True
    has_named_level_zero = (
        Levels.objects.filter(tenant=tenant, level=0).exclude(name="").exists()
    )
    has_root = Administration.objects.filter(
        tenant=tenant, parent__isnull=True
    ).exists()
    return has_named_level_zero and has_root


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    configured = serializers.SerializerMethodField()
    subdomain = serializers.SerializerMethodField()
    administration = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()
    trained = CustomBooleanField(default=False)
    forms = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()
    passcode = serializers.SerializerMethodField()

    @extend_schema_field(UserAdministrationSerializer)
    def get_administration(self, instance: SystemUser):
        if instance.is_superuser:
            # A tenant superadmin is scoped to their own root. Tenant-less
            # superusers (seeders, createsuperuser, legacy deployments)
            # fall back to the old unscoped lookup.
            roots = Administration.objects.filter(parent__isnull=True)
            if instance.tenant_id:
                adm = roots.filter(tenant_id=instance.tenant_id).first()
            else:
                adm = roots.filter(level__level=0).first()
            return UserAdministrationSerializer(instance=adm).data
        # Check if there are multiple user roles at the minimum level
        min_level = instance.user_user_role.aggregate(
            min_level=Min("administration__level__level")
        )["min_level"]
        # Count how many roles are at the minimum level
        roles_at_min_level = instance.user_user_role.filter(
            administration__level__level=min_level
        )
        if roles_at_min_level.count() > 1:
            # Multiple roles at same minimum level, return parent
            first_role = roles_at_min_level.first()
            if first_role and first_role.administration.parent:
                parent = first_role.administration.parent
                return UserAdministrationSerializer(instance=parent).data
        # Order UserRole by administration level and get the first one
        user_role = (
            UserRole.objects.filter(user=instance)
            .order_by("administration__level__level")
            .first()
        )
        if user_role:
            return UserAdministrationSerializer(
                instance=user_role.administration
            ).data
        return None

    @extend_schema_field(UserRoleListSerializer(many=True))
    def get_roles(self, instance: SystemUser):
        user_roles = UserRole.objects.filter(user=instance).all()
        return UserRoleListSerializer(
            instance=user_roles,
            many=True,
        ).data

    @extend_schema_field(OrganisationSerializer)
    def get_organisation(self, instance: SystemUser):
        return OrganisationSerializer(instance=instance.organisation).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance):
        return instance.get_full_name()

    @extend_schema_field(UserFormSerializer(many=True))
    def get_forms(self, instance: SystemUser):
        return UserFormSerializer(
            instance=instance.user_form.all(), many=True
        ).data

    @extend_schema_field(OpenApiTypes.INT)
    def get_last_login(self, instance):
        if instance.last_login:
            return instance.last_login.timestamp()
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_passcode(self, instance: SystemUser):
        mobile_assignment = MobileAssignment.objects.filter(
            user=instance
        ).first()
        if mobile_assignment:
            passcode = CustomPasscode().decode(mobile_assignment.passcode)
            return passcode
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_configured(self, instance: SystemUser):
        return tenant_is_configured(instance.tenant)

    @extend_schema_field(OpenApiTypes.STR)
    def get_subdomain(self, instance: SystemUser):
        # The address this session belongs to. The frontend compares it
        # against the host it is being served on, so that a user who
        # lands on the wrong workspace — or on the tenant-less main
        # site — is sent to their own rather than shown the 403.
        # Empty for a tenant-less account, which has no address of its
        # own and is therefore never redirected.
        return instance.tenant.subdomain if instance.tenant_id else ""

    class Meta:
        model = SystemUser
        fields = [
            "email",
            "name",
            "roles",
            "trained",
            "phone_number",
            "forms",
            "organisation",
            "last_login",
            "passcode",
            "is_superuser",
            "administration",
            "id",
            "configured",
            "subdomain",
        ]


class ListLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Levels
        fields = ["id", "name", "level"]


class UserRoleEditSerializer(serializers.ModelSerializer):
    role = serializers.IntegerField(source="role.id")
    adm_path = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.ANY)
    def get_adm_path(self, instance: UserRole):
        if instance.administration.path:
            adm = instance.administration
            return [int(p) for p in adm.path.split(".") if p.isdigit()] + [
                adm.id
            ]
        return [instance.administration.id]

    class Meta:
        model = UserRole
        fields = ["role", "administration", "adm_path"]


class UserDetailSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    organisation = serializers.SerializerMethodField()
    trained = CustomBooleanField(default=False)
    forms = serializers.SerializerMethodField()
    pending_approval = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()
    pending_batch = serializers.SerializerMethodField()

    @extend_schema_field(UserRoleEditSerializer(many=True))
    def get_roles(self, instance: SystemUser):
        user = self.context.get("user")
        return UserRoleEditSerializer(
            instance=instance.user_user_role.all(),
            many=True,
            context={"user": user},
        ).data

    @extend_schema_field(OrganisationSerializer)
    def get_organisation(self, instance: SystemUser):
        return OrganisationSerializer(instance=instance.organisation).data

    @extend_schema_field(UserFormSerializer(many=True))
    def get_forms(self, instance: SystemUser):
        return UserFormSerializer(
            instance=instance.user_form.all(), many=True
        ).data

    @extend_schema_field(OpenApiTypes.INT)
    def get_pending_approval(self, instance: SystemUser):
        batch_q = Q(approved=False)
        for ur in instance.user_user_role.all():
            adm = ur.administration
            path = (
                adm.path if hasattr(adm, "path") and adm.path else f"{adm.id}."
            )
            batch_q |= Q(
                administration__path__startswith=path,
                approved=False,
            )
        total_batches = DataBatch.objects.filter(batch_q).count()
        return total_batches

    @extend_schema_field(OpenApiTypes.INT)
    def get_data(self, instance: SystemUser):
        return instance.form_data_created.all().count()

    @extend_schema_field(OpenApiTypes.INT)
    def get_pending_batch(self, instance: SystemUser):
        return instance.user_data_batch.filter(approved=False).all().count()

    class Meta:
        model = SystemUser
        fields = [
            "first_name",
            "last_name",
            "email",
            "roles",
            "organisation",
            "trained",
            "phone_number",
            "forms",
            "pending_approval",
            "data",
            "pending_batch",
            "is_superuser",
        ]


class RoleOptionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="name")
    value = serializers.IntegerField(source="id")
    level = serializers.ReadOnlyField(source="administration_level.level")

    class Meta:
        model = Role
        fields = ["label", "value", "level", "administration_level"]


class UpdateProfileSerializer(serializers.ModelSerializer):
    email = CustomEmailField(required=False)
    first_name = CustomCharField(required=False)
    last_name = CustomCharField(required=False)
    phone_number = CustomCharField(required=False)
    organisation = CustomPrimaryKeyRelatedField(
        queryset=Organisation.objects.none(), required=False
    )

    def validate(self, attrs):
        if not any(attrs.values()):
            raise ValidationError("At least one field must be updated")
        return attrs

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields.get("organisation").queryset = Organisation.objects.all()

    class Meta:
        model = SystemUser
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "organisation",
        ]


class ConfigureSerializer(serializers.Serializer):
    # The registrant's name arrives here, not at sign-up: this is the first
    # point at which the email is known to be real.
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    # The top tier's name ("National") and the unit that sits at it
    # ("Kenya") — two different things that are easy to conflate, which is
    # why the form carries examples.
    level_0_name = serializers.CharField(max_length=50)
    root_unit_name = serializers.CharField(max_length=255)


class ResendActivationSerializer(serializers.Serializer):
    # Documents the payload for the schema; the view does not validate it,
    # because an unparseable address must get the same 200 as an unknown one.
    email = serializers.EmailField()


class RegisterSerializer(serializers.Serializer):
    # Phase 1 asks for the minimum that claims a workspace. The registrant's
    # name belongs to the configuration form, which is the first point at
    # which we know the email is real.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    # A valid DNS label, because the subdomain will one day be one:
    # lowercase alphanumerics and hyphens, no leading/trailing hyphen.
    subdomain = serializers.RegexField(
        regex=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$",
        max_length=63,
        error_messages={
            "invalid": (
                "Subdomain may only contain lowercase letters, digits "
                "and hyphens, and cannot start or end with a hyphen"
            )
        },
    )

    def validate_subdomain(self, value):
        """Refuse a subdomain that would collide with the embed host.

        `EMBED_HOST` serves author-pasted third-party markup, and the
        only thing protecting this application from it is that the two
        sit on different origins. A workspace registered at that exact
        host would put them back on the same one: a snippet served there
        could then read the `AUTH_TOKEN` cookie of anyone signed in to
        that workspace, since it is not HttpOnly.

        Compared as whole hosts rather than as labels, so it stays
        correct whatever `EMBED_HOST` is set to, and inert when either
        setting is empty.
        """
        embed = embed_hostname()
        if embed and settings.BASE_DOMAIN:
            candidate = "{0}.{1}".format(value, settings.BASE_DOMAIN).lower()
            if candidate == embed:
                raise serializers.ValidationError(
                    "This subdomain is reserved."
                )
        return value

    # Uniqueness of email and subdomain is left to the database
    # constraints, which the register view turns into a 400 — a
    # pre-check here could not close the race anyway.

    def validate(self, attrs):
        # Run Django's password validators with user context so the
        # similarity validator can compare against the email. There are no
        # names to compare against at this phase.
        user = SystemUser(email=attrs["email"])
        try:
            validate_password(attrs["password"], user=user)
        except django_exceptions.ValidationError as error:
            raise ValidationError({"password": list(error.messages)})
        return attrs
