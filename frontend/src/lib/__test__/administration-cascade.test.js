import { buildAdministrationCascade } from "../constants";

describe("buildAdministrationCascade", () => {
  test("targets the authenticated endpoint with a bearer header", () => {
    const [cascade] = buildAdministrationCascade("tok3n", 7);
    expect(cascade.endpoint).toBe("/api/v1/administration");
    expect(cascade.headers).toEqual({ Authorization: "Bearer tok3n" });
  });

  test("starts at the caller's own root, not a hardcoded 1", () => {
    const [cascade] = buildAdministrationCascade("tok3n", 7);
    expect(cascade.initial).toBe(7);
  });
});
