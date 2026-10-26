import {
  GOALS,
  GOAL_DEFINITIONS,
  TOUR_PATHS,
  getAvailableGoals,
  getRecommendedGoal,
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
