import { AbilityBuilder, createMongoAbility } from "@casl/ability";

const defineAbilityFor = (user) => {
  const { can, cannot, build } = new AbilityBuilder(createMongoAbility);

  // Return basic ability with no permissions if user is null
  if (!user) {
    cannot("manage", "all");
    return build();
  }
  if (user?.is_superuser) {
    can("manage", "all");
  } else if (user) {
    const roles = user?.roles || [];
    const is_approver = roles.filter((r) => r?.is_approver).length > 0;
    const is_submitter = roles.filter((r) => r?.is_submitter).length > 0;
    const is_editor = roles.filter((r) => r?.is_mobile).length > 0;
    const can_delete = roles.filter((r) => r?.can_delete).length > 0;
    const can_invite_user = roles.filter((r) => r?.can_invite_user).length > 0;
    const can_form_builder =
      roles.filter((r) => r?.can_form_builder).length > 0;

    if (is_approver) {
      can("manage", "approvals");
    }
    if (is_submitter) {
      can("manage", "draft");
      can("manage", "submissions");
      can("manage", "mobile");
      can("create", "downloads");
      can("edit", "data");
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
      can("manage", "form-builder");
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
