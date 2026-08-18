import { getLevels } from "../level";
import store from "../../lib/store";

describe("level util", () => {
  test("getLevels returns [] when the store has no levels", () => {
    store.update((s) => {
      s.levels = [];
    });
    expect(getLevels()).toEqual([]);
  });

  test("getLevels returns the store levels", () => {
    const fixture = [{ id: 1, name: "National", level: 0 }];
    store.update((s) => {
      s.levels = fixture;
    });
    expect(getLevels()).toEqual(fixture);
  });
});
