import "@testing-library/jest-dom";
import store from "../store";

describe("Store", () => {
  test("check the initial state", () => {
    const state = {
      isLoggedIn: false,
      user: null,
      filters: {
        trained: null,
        role: null,
        organisation: null,
        query: null,
        attributeType: null,
        entityType: null,
      },
      language: {
        active: "en",
        langs: { en: "English", de: "German" },
      },
      administration: [],
      selectedAdministration: null,
      loadingMap: false,
      allForms: [],
      forms: [],
      levels: [],
      selectedForm: null,
      loadingForm: false,
      questionGroups: [],
      showAdvancedFilters: false,
      advancedFilters: [],
      administrationLevel: null,
    };
    expect(typeof state).toBe("object");

    // Example of property in the store
    expect(store.initialState.user).toBeNull();
    expect(store.initialState.tourOpen).toBe(false);
    expect(store.initialState.tourGoal).toBeNull();
    expect(store.initialState.tourStep).toBe(0);

    // Snapshot
    expect(store.currentState).toMatchSnapshot();
  });
});
