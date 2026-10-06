from django.urls import re_path

from api.v1.v1_users.views import (
    login,
    verify_invite,
    set_user_password,
    list_administration,
    add_user,
    list_users,
    get_profile,
    get_user_roles,
    list_levels,
    UserEditDeleteView,
    forgot_password,
    list_organisations,
    list_organisation_options,
    add_organisation,
    OrganisationEditDeleteView,
    update_profile,
    register,
    activate_account,
    resend_activation,
    configure_project,
    tenant_info,
)
from api.v1.v1_users.admin_views import (
    activate_tenant,
    activate_user,
    deactivate_tenant,
    deactivate_user,
    inspect_tenant,
    operators,
    revoke_operator,
    rename_tenant,
    set_tenant_features,
    tenant_detail,
    tenant_rename_impact,
    tenant_users,
    tenants_summary,
)
from api.v1.v1_users.inspect_views import (
    exchange_code,
    switch_tenant,
    switchable_tenants,
)
from api.v1.v1_profile.views import list_entity_data

urlpatterns = [
    # Console routes first, and every one anchored. The existing
    # patterns in this file are mostly unanchored prefixes -- `users`
    # would otherwise swallow `admin/tenants/1/users`.
    re_path(r"^(?P<version>(v1))/admin/operators$", operators),
    re_path(
        r"^(?P<version>(v1))/admin/operators/(?P<operator_id>[0-9]+)$",
        revoke_operator,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/"
        r"deactivate$",
        deactivate_tenant,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/activate$",
        activate_tenant,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/features$",
        set_tenant_features,
    ),
    # Before the numeric-id pattern. `summary` is not a number so it
    # would not match today, but the ordering makes that a property of
    # the list rather than of the regex.
    re_path(r"^(?P<version>(v1))/admin/tenants/summary$", tenants_summary),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/"
        r"rename-impact$",
        tenant_rename_impact,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/rename$",
        rename_tenant,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/users$",
        tenant_users,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)/inspect$",
        inspect_tenant,
    ),
    # Served on a workspace's host, not the console's, and authorised by
    # the inspection token rather than by a console session.
    re_path(r"^(?P<version>(v1))/inspect/exchange$", exchange_code),
    re_path(r"^(?P<version>(v1))/inspect/tenants$", switchable_tenants),
    re_path(r"^(?P<version>(v1))/inspect/switch$", switch_tenant),
    re_path(
        r"^(?P<version>(v1))/admin/users/(?P<user_id>[0-9]+)/deactivate$",
        deactivate_user,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/users/(?P<user_id>[0-9]+)/activate$",
        activate_user,
    ),
    re_path(
        r"^(?P<version>(v1))/admin/tenants/(?P<tenant_id>[0-9]+)$",
        tenant_detail,
    ),
    # Anchored: unanchored, this pattern also matches /levels-management
    # and — because v1_users is included before v1_profile — would answer
    # it with the read-only list.
    re_path(r"^(?P<version>(v1))/levels$", list_levels),
    re_path(
        r"^(?P<version>(v1))/administration/(?P<administration_id>[0-9]+)",
        list_administration,
    ),
    re_path(r"^(?P<version>(v1))/profile", get_profile),
    re_path(r"^(?P<version>(v1))/login", login),
    re_path(r"^(?P<version>(v1))/tenant-info$", tenant_info),
    re_path(r"^(?P<version>(v1))/register/activate$", activate_account),
    re_path(r"^(?P<version>(v1))/register/configure$", configure_project),
    re_path(
        r"^(?P<version>(v1))/register/resend-activation$", resend_activation
    ),
    re_path(r"^(?P<version>(v1))/register$", register),
    re_path(r"^(?P<version>(v1))/users", list_users),
    re_path(
        r"^(?P<version>(v1))/user/(?P<user_id>[0-9]+)",
        UserEditDeleteView.as_view(),
    ),
    re_path(r"^(?P<version>(v1))/user/forgot-password", forgot_password),
    re_path(r"^(?P<version>(v1))/user/set-password", set_user_password),
    re_path(r"^(?P<version>(v1))/user/roles", get_user_roles),
    re_path(r"^(?P<version>(v1))/user", add_user),
    re_path(
        r"^(?P<version>(v1))/invitation/(?P<invitation_id>.*)$", verify_invite
    ),
    re_path(
        r"^(?P<version>(v1))/organisations",
        list_organisations,
        name="organisations-list",
    ),
    re_path(
        r"^(?P<version>(v1))/organisation/options/(?P<selected_id>[0-9]+)?",
        list_organisation_options,
    ),
    re_path(
        r"^(?P<version>(v1))/organisation/(?P<organisation_id>[0-9]+)",
        OrganisationEditDeleteView.as_view(),
    ),
    re_path(r"^(?P<version>(v1))/organisation", add_organisation),
    re_path(
        (
            r"^(?P<version>(v1))/entity-data/"
            r"(?P<entity_id>[0-9]+)/list/(?P<administration_id>[0-9]+)"
        ),
        list_entity_data,
    ),
    re_path(r"^(?P<version>(v1))/update-profile", update_profile),
]
