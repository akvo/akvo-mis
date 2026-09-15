// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import "@testing-library/jest-dom";
import "jest-canvas-mock";
import store from "./lib/store";

const formsFixture = [
  { id: 1, name: "Example 1", type: 1, version: 1, type_text: "County" },
  { id: 2, name: "Example 2", type: 2, version: 1, type_text: "National" },
];
// Forms are no longer a window global; components read them from the store
// (populated at runtime from GET /api/v1/forms/published). Seed both the
// full list (allForms) and the rendered list (forms) for tests.
store.update((s) => {
  s.allForms = formsFixture;
  s.forms = formsFixture;
  // Levels are fetched at runtime now; seed the store, not a global.
  s.levels = [
    { id: 1, name: "National", level: 0 },
    { id: 2, name: "County", level: 1 },
    { id: 3, name: "Sub-County", level: 2 },
    { id: 4, name: "Ward", level: 3 },
  ];
});

// antd's responsive Row/Col subscribe to media queries on mount and jsdom
// has no matchMedia. Every suite that renders a page needs this, so it
// lives here rather than in each of them.
window.matchMedia =
  window.matchMedia ||
  function () {
    return { matches: false, addListener: () => {}, removeListener: () => {} };
  };

window.visualisation = [];

window.dbadm = [
  {
    full_name: "Indonesia",
    id: 1,
    level: 0,
    name: "Indonesia",
    parent: null,
    path: null,
  },
  {
    full_name: "Indonesia|Jakarta",
    id: 2,
    level: 1,
    name: "Jakarta",
    parent: 1,
    path: "1.",
  },
];

window.appConfig = {
  name: "Test App",
  shortName: "Test",
  showLandingPage: true,
};
