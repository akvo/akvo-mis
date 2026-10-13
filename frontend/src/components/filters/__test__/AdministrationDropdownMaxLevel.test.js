import React from "react";
import { act, cleanup, render, screen } from "@testing-library/react";
import AdministrationDropdown from "../AdministrationDropdown";
import { api } from "../../../lib";
import store from "../../../lib/store";

jest.mock("../../../lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

// Level ids deliberately offset from their depth (27..30) -- the seed shape
// that exposed the id-vs-depth bug: a caller passing the Province level id
// (28) must cap the cascade the same as passing the depth (2), not treat 28
// as a depth and expose every level.
const LEVELS = [
  { id: 27, level: 0, name: "National" },
  { id: 28, level: 1, name: "Province" },
  { id: 29, level: 2, name: "Regency" },
  { id: 30, level: 3, name: "Village" },
];

const CHAIN = [
  {
    id: 1,
    level: 0,
    name: "National",
    children_level_name: "Province",
    children: [
      { id: 11, level: 1, name: "ProvinceA", parent: 1 },
      { id: 12, level: 1, name: "ProvinceB", parent: 1 },
    ],
  },
  {
    id: 11,
    level: 1,
    name: "ProvinceA",
    children_level_name: "Regency",
    children: [{ id: 111, level: 2, name: "RegencyA", parent: 11 }],
  },
  {
    id: 111,
    level: 2,
    name: "RegencyA",
    children_level_name: "Village",
    children: [{ id: 1111, level: 3, name: "VillageA", parent: 111 }],
  },
];

const seed = () => {
  act(() => {
    store.update((s) => {
      s.levels = LEVELS;
      s.administration = CHAIN;
      s.language = { active: "en" };
      s.user = { administration: { id: 1 }, is_superuser: true, roles: [] };
    });
  });
};

const comboboxCount = () => screen.queryAllByRole("combobox").length;

describe("AdministrationDropdown maxLevel normalization", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: CHAIN[0] });
    seed();
  });

  afterEach(cleanup);

  test("a Province level id caps the cascade the same as the depth", () => {
    // persist=true so the component keeps the seeded administration chain
    // instead of refetching the root.
    const { unmount } = render(
      <AdministrationDropdown persist maxLevel={28} onChange={jest.fn()} />
    );
    // Province id 28 -> depth 2 -> only the National select renders. Before
    // normalization, 28 was read as a depth and all three levels rendered.
    expect(comboboxCount()).toBe(1);
    unmount();

    render(
      <AdministrationDropdown persist maxLevel={2} onChange={jest.fn()} />
    );
    expect(comboboxCount()).toBe(1);
  });

  test("a deeper level id renders one more select", () => {
    render(
      <AdministrationDropdown persist maxLevel={29} onChange={jest.fn()} />
    );
    // Regency id 29 -> depth 3 -> National + Province selects.
    expect(comboboxCount()).toBe(2);
  });
});
