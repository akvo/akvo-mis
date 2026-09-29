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

describe("ability for an inspection session", () => {
  const inspecting = {
    id: 1,
    is_superuser: true,
    is_inspecting: true,
    roles: [],
  };

  it("can read", () => {
    expect(ability(inspecting).can("read", "data")).toBe(true);
  });

  it("cannot write anything", () => {
    const can = ability(inspecting);
    expect(can.can("edit", "data")).toBe(false);
    expect(can.can("upload", "data")).toBe(false);
    expect(can.can("delete", "data")).toBe(false);
    expect(can.can("create", "dashboard")).toBe(false);
    expect(can.can("manage", "user")).toBe(false);
  });

  it("leaves an ordinary superadmin alone", () => {
    const owner = { id: 2, is_superuser: true, roles: [] };
    expect(ability(owner).can("edit", "data")).toBe(true);
  });
});
