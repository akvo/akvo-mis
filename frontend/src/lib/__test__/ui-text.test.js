import "@testing-library/jest-dom";
import uiText from "../ui-text";

describe("UI Text", () => {
  test("check text languages", () => {
    expect(uiText).toHaveProperty("en");
    expect(uiText).toHaveProperty("es");
    expect(uiText).toHaveProperty("fr");
    expect(uiText).toMatchSnapshot();
  });
});
