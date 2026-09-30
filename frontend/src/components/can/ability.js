import { AbilityBuilder, createMongoAbility } from "@casl/ability";

const defineAbilityFor = (user) => {
  const { can, cannot, build } = new AbilityBuilder(createMongoAbility);

  // Return basic ability with no permissions if user is null
  if (!user) {
    cannot("manage", "all");
    return build();
  }
  // A read-only cross-workspace session. Checked before is_superuser,
  // which the backend sets on an inspecting operator so that the
  // workspace's own pages render at all.
  //
  // The authority is kept and the write verbs are subtracted, rather
  // than replaced with `can("read", "all")`. In this codebase `manage`
  // is what the sidebar gates whole sections on -- users, roles,
  // drafts, submissions, approvals, master data, the mobile app -- so
  // granting only `read` takes away half the navigation, and an
  // operator on a support call about master data would find no Master
  // Data menu and no way to tell whether that is the inspection or the
  // customer's configuration. A support view that looks right and
  // behaves wrong is the failure this whole feature exists to avoid.
  //
  // Presentation only either way: the server refuses these writes
  // whether or not the browser attempts them. What this buys is an
  // operator who is not offered buttons that will 403.
  if (user?.is_inspecting) {
    can("manage", "all");
    cannot(["create", "edit", "delete", "upload", "publish"], "all");
    // `manage dashboard` is the one place `manage` gates a write rather
    // than a section: DashboardList reads it as "may create/edit/delete"
    // alongside the granular verbs, so leaving it granted would offer
    // three buttons that 403. Withdrawing it takes every dashboard
    // action with it -- `manage` in a rule is a wildcard, not an action
    // -- so reading is granted back on the next line, which is what the
    // sidebar's `manage || read` gate then finds.
    cannot("manage", "dashboard");
    can("read", "dashboard");
    return build();
  }
  if (user?.is_superuser) {
    can("manage", "all");
  } else if (user) {
    const roles = user?.roles || [];
    const is_approver = roles.filter((r) => r?.is_approver).length > 0;
    const is_submitter = roles.filter((r) => r?.is_submitter).length > 0;
    const is_editor = roles.filter((r) => r?.is_editor).length > 0;
    const can_delete = roles.filter((r) => r?.can_delete).length > 0;
    const can_invite_user = roles.filter((r) => r?.can_invite_user).length > 0;
    const can_form_builder =
      roles.filter((r) => r?.can_form_builder).length > 0;
    const can_form_delete = roles.filter((r) => r?.can_form_delete).length > 0;
    const can_form_create = roles.filter((r) => r?.can_form_create).length > 0;
    const can_form_edit = roles.filter((r) => r?.can_form_edit).length > 0;
    const can_form_publish =
      roles.filter((r) => r?.can_form_publish).length > 0;

    if (is_approver) {
      can("manage", "approvals");
    }
    if (is_submitter) {
      can("manage", "draft");
      can("manage", "submissions");
      can("manage", "mobile");
      can("create", "downloads");
      can("edit", "data");
      can("upload", "data");
    }
    if (is_editor) {
      can("edit", "data");
      can("upload", "data");
    }
    if (can_delete) {
      can("delete", "data");
    }
    if (can_invite_user) {
      can("manage", "user");
    }
    if (can_form_builder) {
      can("read", "form-builder");
    }
    if (can_form_delete) {
      can("delete", "form-builder");
    }
    if (can_form_create) {
      can("create", "form-builder");
    }
    if (can_form_edit) {
      can("edit", "form-builder");
    }
    if (can_form_publish) {
      can("publish", "form-builder");
    }

    const can_dashboard_create =
      roles.filter((r) => r?.can_dashboard_create).length > 0;
    const can_dashboard_edit =
      roles.filter((r) => r?.can_dashboard_edit).length > 0;
    const can_dashboard_delete =
      roles.filter((r) => r?.can_dashboard_delete).length > 0;
    const can_dashboard_publish = roles.some((r) => r?.can_dashboard_publish);

    if (can_dashboard_create) {
      can("create", "dashboard");
    }
    if (can_dashboard_edit) {
      can("edit", "dashboard");
    }
    if (can_dashboard_delete) {
      can("delete", "dashboard");
    }

    // "read dashboard" is what gates the builder: the sidebar menu and
    // the /control-center/dashboard route both hang off it. It is
    // deliberately not `can_dashboard_view` any more — a role with only
    // View is a consumer, who reads dashboards through the header menu
    // and never opens the builder.
    if (
      can_dashboard_create ||
      can_dashboard_edit ||
      can_dashboard_publish ||
      can_dashboard_delete
    ) {
      can("read", "dashboard");
    }

    can("read", "data");
    can("read", "downloads");
    can("read", "approvals");
    can("read", "approvers");
    can("manage", "form");
    can("manage", "control-center");
    can("manage", "profile");

    cannot("manage", "roles");
    cannot("manage", "master-data");
    cannot("manage", "settings");
  }
  return build();
};

export const ability = (user) => {
  return defineAbilityFor(user);
};
