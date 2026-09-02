import { ability } from "../ability";

const userWith = (flags) => ({ roles: [{ ...flags }] });

describe("dashboard abilities", () => {
  it("does not open the builder for a view-only role", () => {
    const a = ability(userWith({ can_dashboard_view: true }));
    expect(a.can("read", "dashboard")).toBe(false);
  });

  it("opens the builder for an edit-only role", () => {
    const a = ability(userWith({ can_dashboard_edit: true }));
    expect(a.can("read", "dashboard")).toBe(true);
  });

  it("opens the builder for a publish-only role", () => {
    const a = ability(userWith({ can_dashboard_publish: true }));
    expect(a.can("read", "dashboard")).toBe(true);
  });
});
