import {
  GOALS,
  GOAL_DEFINITIONS,
  TOUR_PATHS,
  getAvailableGoals,
  getRecommendedGoal,
  getTourPath,
  getTotalStepsForGoal,
} from "../tourConfig";

describe("tourConfig - Role Engine & Goal Routing", () => {
  describe("getAvailableGoals", () => {
    test("returns setup, review, explore for superuser", () => {
      const user = { is_superuser: true, roles: [] };
      const goals = getAvailableGoals(user);
      expect(goals).toEqual([GOALS.SETUP, GOALS.REVIEW, GOALS.EXPLORE]);
    });

    test("returns setup, review, explore for admin role by capability (can_form_create)", () => {
      const user = {
        is_superuser: false,
        roles: [{ can_form_create: true }],
      };
      const goals = getAvailableGoals(user);
      expect(goals).toEqual([GOALS.SETUP, GOALS.REVIEW, GOALS.EXPLORE]);
    });

    test("returns setup, review, explore for admin role by name", () => {
      const user = {
        is_superuser: false,
        roles: [{ role: "National Admin" }],
      };
      const goals = getAvailableGoals(user);
      expect(goals).toEqual([GOALS.SETUP, GOALS.REVIEW, GOALS.EXPLORE]);
    });

    test("returns review, explore for approver who is not admin", () => {
      const user = {
        is_superuser: false,
        roles: [{ is_approver: true }],
      };
      const goals = getAvailableGoals(user);
      expect(goals).toEqual([GOALS.REVIEW, GOALS.EXPLORE]);
    });

    test("returns only explore for data viewer / general user", () => {
      const user = {
        is_superuser: false,
        roles: [{ role: "Data Viewer", can_dashboard_view: true }],
      };
      const goals = getAvailableGoals(user);
      expect(goals).toEqual([GOALS.EXPLORE]);
    });

    test("returns only explore for user with empty roles or null", () => {
      expect(getAvailableGoals(null)).toEqual([GOALS.EXPLORE]);
      expect(getAvailableGoals({ roles: [] })).toEqual([GOALS.EXPLORE]);
      expect(getAvailableGoals({ is_superuser: false, roles: [null] })).toEqual(
        [GOALS.EXPLORE]
      );
    });
  });

  describe("getRecommendedGoal", () => {
    test("recommends setup for superuser", () => {
      const user = { is_superuser: true };
      expect(getRecommendedGoal(user)).toBe(GOALS.SETUP);
    });

    test("recommends setup for admin role", () => {
      const user = { is_superuser: false, roles: [{ can_form_builder: true }] };
      expect(getRecommendedGoal(user)).toBe(GOALS.SETUP);
    });

    test("recommends review for approver", () => {
      const user = { is_superuser: false, roles: [{ is_approver: true }] };
      expect(getRecommendedGoal(user)).toBe(GOALS.REVIEW);
    });

    test("recommends explore for data viewer or unprivileged user", () => {
      expect(getRecommendedGoal(null)).toBe(GOALS.EXPLORE);
      const user = { is_superuser: false, roles: [] };
      expect(getRecommendedGoal(user)).toBe(GOALS.EXPLORE);
    });
  });

  describe("getTotalStepsForGoal", () => {
    test("calculates correct total steps including Step 1 Goal Picker", () => {
      expect(getTotalStepsForGoal(GOALS.SETUP)).toBe(5);
      expect(getTotalStepsForGoal(GOALS.REVIEW)).toBe(4);
      expect(getTotalStepsForGoal(GOALS.EXPLORE)).toBe(5);
    });

    test("defaults to 5 steps for unknown goal", () => {
      expect(getTotalStepsForGoal("unknown")).toBe(5);
    });

    test("adapts total steps dynamically when user lacks dashboard permission in explore goal", () => {
      const viewerAbility = {
        can: (action, subject) => {
          if (subject === "dashboard") {
            return false;
          }
          if (subject === "data" || subject === "downloads") {
            return true;
          }
          return false;
        },
      };
      // Explore has 3 valid path steps for viewer + 1 Welcome modal = 4 total steps
      expect(getTotalStepsForGoal(GOALS.EXPLORE, viewerAbility)).toBe(4);
    });
  });

  describe("getTourPath - Role-Adaptive Permissions & Dynamic CTA", () => {
    test("returns raw basePath when ability is null or not provided", () => {
      expect(getTourPath(GOALS.EXPLORE, null)).toEqual(
        TOUR_PATHS[GOALS.EXPLORE]
      );
      expect(getTourPath(GOALS.EXPLORE)).toEqual(TOUR_PATHS[GOALS.EXPLORE]);
    });

    test("returns empty array for unknown goal", () => {
      expect(getTourPath("unknown", null)).toEqual([]);
    });

    test("includes all steps and create dashboard CTA for admin/superuser ability", () => {
      const adminAbility = {
        can: () => true,
      };
      const path = getTourPath(GOALS.EXPLORE, adminAbility);
      expect(path).toHaveLength(4);
      expect(path.map((s) => s.targetSelector)).toEqual([
        '[data-tour="sidebar-data"]',
        '[data-tour="sidebar-dashboards"]',
        '[data-tour="sidebar-downloads"]',
        ".chatbot-fab-btn",
      ]);
      const lastStep = path[3];
      expect(lastStep.ctaLabelKey).toBe("tourExploreFinalBtn");
      expect(lastStep.ctaRoute).toBe("/control-center/dashboard");
      expect(lastStep.ctaState).toEqual({ openCreate: true });
    });

    test("filters out sidebar-dashboards and provides Browse Data CTA for Data Viewer", () => {
      const viewerAbility = {
        can: (action, subject) => {
          if (subject === "dashboard") {
            return false;
          }
          if (subject === "data" || subject === "downloads") {
            return true;
          }
          return false;
        },
      };
      const path = getTourPath(GOALS.EXPLORE, viewerAbility);
      expect(path).toHaveLength(3);
      expect(path.map((s) => s.targetSelector)).toEqual([
        '[data-tour="sidebar-data"]',
        '[data-tour="sidebar-downloads"]',
        ".chatbot-fab-btn",
      ]);
      const lastStep = path[2];
      expect(lastStep.ctaLabelKey).toBe("tourExploreViewDataBtn");
      expect(lastStep.ctaRoute).toBe("/control-center/data");
      expect(lastStep.ctaState).toBeNull();
    });

    test("falls back to Browse Data CTA on setup path if user cannot create forms", () => {
      const restrictedAbility = {
        can: (action, subject) => {
          if (subject === "form-builder" && action === "create") {
            return false;
          }
          return true;
        },
      };
      const path = getTourPath(GOALS.SETUP, restrictedAbility);
      const lastStep = path[path.length - 1];
      expect(lastStep.ctaLabelKey).toBe("tourExploreViewDataBtn");
      expect(lastStep.ctaRoute).toBe("/control-center/data");
    });

    test("falls back to Browse Data CTA on review path if user cannot manage approvals", () => {
      const restrictedAbility = {
        can: (action, subject) => {
          if (subject === "approvals" && action === "manage") {
            return false;
          }
          return true;
        },
      };
      const path = getTourPath(GOALS.REVIEW, restrictedAbility);
      const lastStep = path[path.length - 1];
      expect(lastStep.ctaLabelKey).toBe("tourExploreViewDataBtn");
      expect(lastStep.ctaRoute).toBe("/control-center/data");
    });
  });

  describe("TOUR_PATHS integrity", () => {
    test("setup path has 4 steps and ends on Get help with form builder create CTA", () => {
      const steps = TOUR_PATHS[GOALS.SETUP];
      expect(steps).toHaveLength(4);
      // Step 2 (first in path array)
      expect(steps[0].titleKey).toBe("tourSetupStep1Title");
      // Step 3 (second in path array) has copy app link
      expect(steps[1].action).toBe("copy_app_link");
      // Step 5 (last in path array)
      expect(steps[3].titleKey).toBe("tourGetHelpTitle");
      expect(steps[3].ctaRoute).toBe("/control-center/form-builder/create");
    });

    test("review path has 3 steps and ends on approvals CTA", () => {
      const steps = TOUR_PATHS[GOALS.REVIEW];
      expect(steps).toHaveLength(3);
      expect(steps[0].titleKey).toBe("tourReviewStep1Title");
      expect(steps[2].titleKey).toBe("tourGetHelpTitle");
      expect(steps[2].ctaRoute).toBe("/control-center/approvals");
    });

    test("explore path has 4 steps and ends on dashboard builder CTA with create state", () => {
      const steps = TOUR_PATHS[GOALS.EXPLORE];
      expect(steps).toHaveLength(4);
      expect(steps[0].titleKey).toBe("tourExploreStep1Title");
      expect(steps[3].titleKey).toBe("tourGetHelpTitle");
      expect(steps[3].ctaRoute).toBe("/control-center/dashboard");
      expect(steps[3].ctaState).toEqual({ openCreate: true });
    });
  });

  describe("GOAL_DEFINITIONS", () => {
    test("defines setup, review, explore with title and description keys", () => {
      expect(GOAL_DEFINITIONS[GOALS.SETUP]).toBeDefined();
      expect(GOAL_DEFINITIONS[GOALS.REVIEW]).toBeDefined();
      expect(GOAL_DEFINITIONS[GOALS.EXPLORE]).toBeDefined();

      expect(GOAL_DEFINITIONS[GOALS.SETUP].key).toBe("setup");
      expect(GOAL_DEFINITIONS[GOALS.REVIEW].key).toBe("review");
      expect(GOAL_DEFINITIONS[GOALS.EXPLORE].key).toBe("explore");
    });
  });
});
