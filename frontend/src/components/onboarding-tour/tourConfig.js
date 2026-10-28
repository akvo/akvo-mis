/**
 * Tour configuration & role routing engine for Akvo MIS onboarding tour.
 * Corresponds to [#561] TOUR-001 specification.
 */

export const GOALS = Object.freeze({
  SETUP: "setup",
  REVIEW: "review",
  EXPLORE: "explore",
});

/**
 * Evaluates whether a user has administrative privileges.
 * @param {object|null} user
 * @returns {boolean}
 */
export const isUserAdmin = (user) => {
  if (!user) {
    return false;
  }
  if (user.is_superuser) {
    return true;
  }
  const roles = user.roles || [];
  return roles.some((r) => {
    if (!r) {
      return false;
    }
    const roleName = (r.role || "").toLowerCase();
    return (
      r.can_form_create ||
      r.can_form_builder ||
      r.can_invite_user ||
      roleName.includes("admin")
    );
  });
};

/**
 * Evaluates whether a user has approver privileges.
 * @param {object|null} user
 * @returns {boolean}
 */
export const isUserApprover = (user) => {
  if (!user) {
    return false;
  }
  const roles = user.roles || [];
  return roles.some((r) => Boolean(r && r.is_approver));
};

/**
 * Returns available tour goals for the current user based on permissions.
 * - Super admin, admin: setup, review, explore
 * - Approver: review, explore
 * - Data viewer / everyone else: explore
 * @param {object|null} user
 * @returns {string[]}
 */
export const getAvailableGoals = (user) => {
  if (!user) {
    return [GOALS.EXPLORE];
  }
  if (isUserAdmin(user)) {
    return [GOALS.SETUP, GOALS.REVIEW, GOALS.EXPLORE];
  }
  if (isUserApprover(user)) {
    return [GOALS.REVIEW, GOALS.EXPLORE];
  }
  return [GOALS.EXPLORE];
};

/**
 * Returns recommended tour goal for the current user.
 * - Super admin, admin: setup
 * - Approver: review
 * - Data viewer / everyone else: explore
 * @param {object|null} user
 * @returns {string}
 */
export const getRecommendedGoal = (user) => {
  if (!user) {
    return GOALS.EXPLORE;
  }
  if (isUserAdmin(user)) {
    return GOALS.SETUP;
  }
  if (isUserApprover(user)) {
    return GOALS.REVIEW;
  }
  return GOALS.EXPLORE;
};

/**
 * Returns total steps count for a given goal (including Step 1 Goal Picker),
 * optionally adapting to user ability permissions.
 * - setup: 5 (Step 1 + 4 path steps)
 * - review: 4 (Step 1 + 3 path steps)
 * - explore: 5 (Step 1 + 4 path steps, or fewer if permissions are restricted)
 * @param {string} goal
 * @param {object|null} ability
 * @returns {number}
 */
export const getTotalStepsForGoal = (goal, ability = null) => {
  const path = getTourPath(goal, ability);
  if (path && path.length > 0) {
    return path.length + 1;
  }
  return 5;
};

export const GOAL_DEFINITIONS = Object.freeze({
  [GOALS.SETUP]: {
    key: GOALS.SETUP,
    titleKey: "tourGoalSetupTitle",
    descKey: "tourGoalSetupDesc",
  },
  [GOALS.REVIEW]: {
    key: GOALS.REVIEW,
    titleKey: "tourGoalReviewTitle",
    descKey: "tourGoalReviewDesc",
  },
  [GOALS.EXPLORE]: {
    key: GOALS.EXPLORE,
    titleKey: "tourGoalExploreTitle",
    descKey: "tourGoalExploreDesc",
  },
});

export const TOUR_PATHS = Object.freeze({
  [GOALS.SETUP]: [
    {
      targetSelector: '[data-tour="sidebar-form-builder"]',
      fallbackSelector: "#menu-form-builder",
      titleKey: "tourSetupStep1Title",
      descKey: "tourSetupStep1Desc",
      illustration: "form",
      permission: (ability) => ability.can("read", "form-builder"),
    },
    {
      targetSelector: '[data-tour="sidebar-download-apps"]',
      fallbackSelector: "#menu-download-apps",
      titleKey: "tourSetupStep2Title",
      descKey: "tourSetupStep2Desc",
      action: "copy_app_link",
      actionLabelKey: "tourCopyAppLink",
      permission: (ability) => ability.can("manage", "mobile"),
    },
    {
      targetSelector: "#panel-submission",
      fallbackSelector: '[data-tour="sidebar-data"]',
      titleKey: "tourSetupStep3Title",
      descKey: "tourSetupStep3Desc",
      permission: (ability) =>
        ability.can("manage", "submissions") || ability.can("read", "data"),
    },
    {
      targetSelector: ".chatbot-fab-btn",
      fallbackSelector: '[data-tour="sidebar-documentation"]',
      titleKey: "tourGetHelpTitle",
      descKey: "tourGetHelpDesc",
      ctaLabelKey: "tourSetupFinalBtn",
      ctaRoute: "/control-center/form-builder/create",
      dynamicCta: (ability) => {
        if (ability.can("create", "form-builder")) {
          return {
            ctaLabelKey: "tourSetupFinalBtn",
            ctaRoute: "/control-center/form-builder/create",
          };
        }
        return {
          ctaLabelKey: "tourExploreViewDataBtn",
          ctaRoute: "/control-center/data",
        };
      },
    },
  ],
  [GOALS.REVIEW]: [
    {
      targetSelector: "#panel-approvals",
      fallbackSelector: '[data-tour="sidebar-data"]',
      titleKey: "tourReviewStep1Title",
      descKey: "tourReviewStep1Desc",
      permission: (ability) =>
        ability.can("manage", "approvals") || ability.can("read", "approvals"),
    },
    {
      targetSelector: '[data-tour="sidebar-data"]',
      fallbackSelector: "#menu-data",
      titleKey: "tourReviewStep2Title",
      descKey: "tourReviewStep2Desc",
      permission: (ability) => ability.can("read", "data"),
    },
    {
      targetSelector: ".chatbot-fab-btn",
      fallbackSelector: '[data-tour="sidebar-documentation"]',
      titleKey: "tourGetHelpTitle",
      descKey: "tourGetHelpDesc",
      ctaLabelKey: "tourReviewFinalBtn",
      ctaRoute: "/control-center/approvals",
      dynamicCta: (ability) => {
        if (ability.can("manage", "approvals")) {
          return {
            ctaLabelKey: "tourReviewFinalBtn",
            ctaRoute: "/control-center/approvals",
          };
        }
        return {
          ctaLabelKey: "tourExploreViewDataBtn",
          ctaRoute: "/control-center/data",
        };
      },
    },
  ],
  [GOALS.EXPLORE]: [
    {
      targetSelector: '[data-tour="sidebar-data"]',
      fallbackSelector: "#menu-data",
      titleKey: "tourExploreStep1Title",
      descKey: "tourExploreStep1Desc",
      permission: (ability) => ability.can("read", "data"),
    },
    {
      targetSelector: '[data-tour="sidebar-dashboards"]',
      fallbackSelector: "#menu-dashboards",
      titleKey: "tourExploreStep2Title",
      descKey: "tourExploreStep2Desc",
      permission: (ability) =>
        ability.can("read", "dashboard") || ability.can("manage", "dashboard"),
    },
    {
      targetSelector: '[data-tour="sidebar-downloads"]',
      fallbackSelector: "#menu-downloads",
      titleKey: "tourExploreStep3Title",
      descKey: "tourExploreStep3Desc",
      permission: (ability) => ability.can("read", "downloads"),
    },
    {
      targetSelector: ".chatbot-fab-btn",
      fallbackSelector: '[data-tour="sidebar-documentation"]',
      titleKey: "tourGetHelpTitle",
      descKey: "tourGetHelpDesc",
      ctaLabelKey: "tourExploreFinalBtn",
      ctaRoute: "/control-center/dashboard",
      ctaState: { openCreate: true },
      dynamicCta: (ability) => {
        if (
          ability.can("create", "dashboard") ||
          ability.can("manage", "dashboard")
        ) {
          return {
            ctaLabelKey: "tourExploreFinalBtn",
            ctaRoute: "/control-center/dashboard",
            ctaState: { openCreate: true },
          };
        }
        return {
          ctaLabelKey: "tourExploreViewDataBtn",
          ctaRoute: "/control-center/data",
          ctaState: null,
        };
      },
    },
  ],
});

/**
 * Resolves the active tour path for a given goal, dynamically filtering steps
 * and tailoring final CTAs based on CASL ability permissions.
 * @param {string} goal
 * @param {object|null} ability
 * @returns {Array<object>}
 */
export const getTourPath = (goal, ability = null) => {
  const basePath = TOUR_PATHS[goal] || [];
  if (!ability || typeof ability.can !== "function") {
    return basePath;
  }

  const filtered = basePath.filter((step) => {
    if (!step.permission) {
      return true;
    }
    return step.permission(ability);
  });

  return filtered.map((step) => {
    if (step.dynamicCta) {
      return {
        ...step,
        ...step.dynamicCta(ability),
      };
    }
    return step;
  });
};
