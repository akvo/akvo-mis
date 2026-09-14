import { normalizeWebformQuestion } from "../form-helpers";

describe("normalizeWebformQuestion", () => {
  test("administration cascade keeps type cascade", () => {
    const q = normalizeWebformQuestion({
      id: 104,
      type: "cascade",
      extra: { type: "administration" },
      api: { endpoint: "/api/v1/administration", initial: 1 },
    });
    expect(q.type).toBe("cascade");
    expect(q.extra).toBeUndefined();
    expect(q.api.endpoint).toBe("/api/v1/administration");
  });

  test("entity cascade keeps extra and type cascade", () => {
    const q = normalizeWebformQuestion({
      id: 1,
      type: "cascade",
      extra: { type: "entity", name: "School", parentId: 2 },
    });
    expect(q.type).toBe("cascade");
    expect(q.extra).toEqual({ type: "entity", name: "School", parentId: 2 });
  });

  test("allowOther adds allowOtherText and flattens extra", () => {
    const q = normalizeWebformQuestion({
      id: 1,
      type: "option",
      extra: { allowOther: true },
    });
    expect(q.allowOther).toBe(true);
    expect(q.allowOtherText).toBe("Enter any OTHER value");
    expect(q.type).toBe("option");
  });

  test("allowOtherText configured in the builder wins over the default", () => {
    const q = normalizeWebformQuestion({
      id: 1,
      type: "option",
      extra: { allowOther: true, allowOtherText: "Specify" },
    });
    expect(q.allowOtherText).toBe("Specify");
  });

  test("question without extra is returned unchanged", () => {
    expect(normalizeWebformQuestion({ id: 1, type: "input" })).toEqual({
      id: 1,
      type: "input",
    });
  });
});
