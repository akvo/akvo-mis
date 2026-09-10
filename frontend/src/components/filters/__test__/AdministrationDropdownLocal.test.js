import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import AdministrationDropdownLocal from "../AdministrationDropdownLocal";
import { api } from "../../../lib";
import store from "../../../lib/store";

jest.mock("../../../lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

const ROOT_ADMIN = {
  id: 1,
  name: "Indonesia",
  level: 0,
  parent: null,
  children_level_name: "Province",
  children: [
    { id: 11, name: "Jakarta", level: 1, parent: 1 },
    { id: 12, name: "Bali", level: 1, parent: 1 },
  ],
};

const PROVINCE_DETAIL = {
  id: 11,
  name: "Jakarta",
  level: 1,
  parent: 1,
  children_level_name: "City",
  children: [
    { id: 111, name: "Jakarta Selatan", level: 2, parent: 11 },
    { id: 112, name: "Jakarta Pusat", level: 2, parent: 11 },
  ],
};

const seedUser = (overrides = {}) => {
  act(() => {
    store.update((s) => {
      s.user = {
        administration: { id: 1 },
        is_superuser: true,
        roles: [],
        ...overrides,
      };
    });
  });
};

describe("AdministrationDropdownLocal", () => {
  beforeEach(() => {
    api.get.mockReset();
    act(() => {
      store.update((s) => {
        s.administration = [];
        s.user = null;
      });
    });
  });

  afterEach(() => {
    cleanup();
  });

  test("fetches root admin on mount and renders the first cascade <Select>", async () => {
    seedUser();
    api.get.mockImplementation((url) => {
      if (url === "administration/1") {
        return Promise.resolve({ data: ROOT_ADMIN });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    render(<AdministrationDropdownLocal onChange={jest.fn()} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/1");
    });
    // The cascade renders one <Select> per level with children — the
    // root admin has children, so we expect exactly one combobox here.
    expect(await screen.findByRole("combobox")).toBeTruthy();
  });

  test("picking a child fetches its detail, appends to the cascade, and emits the deepest level via onChange", async () => {
    seedUser();
    const onChange = jest.fn();
    api.get.mockImplementation((url) => {
      if (url === "administration/1") {
        return Promise.resolve({ data: ROOT_ADMIN });
      }
      if (url === "administration/11") {
        return Promise.resolve({ data: PROVINCE_DETAIL });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    render(<AdministrationDropdownLocal onChange={onChange} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/1");
    });

    const provinceCombobox = await screen.findByRole("combobox");
    fireEvent.mouseDown(provinceCombobox);
    const jakartaOption = await screen.findByText("Jakarta");
    fireEvent.click(jakartaOption);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/11");
    });
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ id: 11, name: "Jakarta" })
      );
    });
  });

  test("never writes to store.administration during mount or selection", async () => {
    seedUser();
    api.get.mockImplementation((url) => {
      if (url === "administration/1") {
        return Promise.resolve({ data: ROOT_ADMIN });
      }
      if (url === "administration/11") {
        return Promise.resolve({ data: PROVINCE_DETAIL });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const before = store.getRawState().administration;

    render(<AdministrationDropdownLocal onChange={jest.fn()} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/1");
    });

    const provinceCombobox = await screen.findByRole("combobox");
    fireEvent.mouseDown(provinceCombobox);
    const jakartaOption = await screen.findByText("Jakarta");
    fireEvent.click(jakartaOption);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/11");
    });

    // Interactions must NOT mutate the global admin state — the whole
    // point of this component is to keep selection local.
    expect(store.getRawState().administration).toBe(before);
  });

  test("non-superuser with role-scoped admins only sees children inside their assigned role", async () => {
    seedUser({
      is_superuser: false,
      roles: [
        {
          administration: { level_id: 1, id: 11 },
        },
      ],
    });
    api.get.mockImplementation((url) => {
      if (url === "administration/1") {
        return Promise.resolve({ data: ROOT_ADMIN });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    render(<AdministrationDropdownLocal onChange={jest.fn()} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/1");
    });

    const provinceCombobox = await screen.findByRole("combobox");
    fireEvent.mouseDown(provinceCombobox);
    expect(await screen.findByText("Jakarta")).toBeTruthy();
    expect(screen.queryByText("Bali")).toBeNull();
  });

  test("fetches root admin from rootId prop when user is not logged in", async () => {
    // store.user is null by default in beforeEach
    api.get.mockImplementation((url) => {
      if (url === "administration/1") {
        return Promise.resolve({ data: ROOT_ADMIN });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    render(<AdministrationDropdownLocal rootId={1} onChange={jest.fn()} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("administration/1");
    });
    expect(await screen.findByRole("combobox")).toBeTruthy();
  });
});
