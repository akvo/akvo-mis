import { withoutMonitoringForms } from "../AddUser";

// The questionnaire select offers registration forms only; the monitoring
// forms the backend adds under them must not show up as bare ids.
const FORMS = [
  { id: 1, name: "Registration", content: { parent: null } },
  { id: 2, name: "Monitoring", content: { parent: 1 } },
];

test("monitoring forms are dropped, registration forms kept", () => {
  expect(withoutMonitoringForms([1, 2], FORMS)).toEqual([1]);
});

test("a form the list does not know yet is kept", () => {
  expect(withoutMonitoringForms([1, 9], FORMS)).toEqual([1, 9]);
});

test("no saved forms is an empty list", () => {
  expect(withoutMonitoringForms(null, FORMS)).toEqual([]);
});
