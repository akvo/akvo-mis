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
    expect(can.can("publish", "form-builder")).toBe(false);
    expect(can.can("create", "form-builder")).toBe(false);
  });

  // The checks the sidebar actually makes. Asserted as the sidebar
  // spells them, not as "manage is granted": an inspecting operator who
  // cannot reach Master Data cannot answer a support call about it, and
  // nothing on screen would tell them the menu is short.
  it("keeps every section the workspace's own sidebar offers", () => {
    const can = ability(inspecting);
    [
      "user",
      "roles",
      "draft",
      "submissions",
      "approvals",
      "master-data",
      "mobile",
      "control-center",
    ].forEach((subject) => {
      expect([subject, can.can("manage", subject)]).toEqual([subject, true]);
    });
    expect(can.can("read", "form-builder")).toBe(true);
    expect(can.can("read", "downloads")).toBe(true);
    expect(can.can("manage", "dashboard") || can.can("read", "dashboard")).toBe(
      true
    );
  });

  // The three gates DashboardList uses, spelled as it spells them. It
  // reads `manage dashboard` as a write grant, which is why the branch
  // subtracts that one on top of the verbs.
  it("offers no dashboard write control", () => {
    const can = ability(inspecting);
    expect(
      can.can("manage", "dashboard") || can.can("create", "dashboard")
    ).toBe(false);
    expect(can.can("manage", "dashboard") || can.can("edit", "dashboard")).toBe(
      false
    );
    expect(
      can.can("manage", "dashboard") || can.can("delete", "dashboard")
    ).toBe(false);
  });

  it("leaves an ordinary superadmin alone", () => {
    const owner = { id: 2, is_superuser: true, roles: [] };
    expect(ability(owner).can("edit", "data")).toBe(true);
    expect(ability(owner).can("manage", "settings")).toBe(true);
  });

  it("denies settings management to regular users", () => {
    const user = { id: 3, is_superuser: false, roles: [{ is_editor: true }] };
    expect(ability(user).can("manage", "settings")).toBe(false);
  });
});
