import { fireEvent, render, screen, within } from "@testing-library/react";
import { act } from "react-dom/test-utils";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import Tenants from "../Tenants";
import "@testing-library/jest-dom";

jest.mock("axios");

const rows = [
  {
    id: 1,
    subdomain: "mohhs",
    name: "Ministry of Health HSS",
    state: "active",
    features: { embedded_dashboard: true },
    users: 47,
    forms: 12,
    dashboards: 5,
    datapoints: 128430,
    devices: 23,
  },
  {
    id: 2,
    subdomain: "sleman",
    name: "Sleman Regency",
    state: "suspended",
    features: {},
    users: 8,
    forms: 3,
    dashboards: 1,
    datapoints: 12004,
    devices: 4,
  },
];

// The summary deliberately disagrees with the sum of `rows`. Every
// assertion about a total therefore distinguishes "rendered what the
// server said" from "added up what is on screen" -- a fixture whose
// numbers agreed could not tell the two implementations apart.
const summary = {
  users: 900,
  forms: 800,
  dashboards: 700,
  datapoints: 600000,
  devices: 500,
};

const envelope = (overrides = {}) => ({
  status: 200,
  data: {
    current: 1,
    total: 2,
    total_page: 1,
    summary,
    data: rows,
    ...overrides,
  },
});

// The URL of the most recent GET the component issued. `api.get` passes
// no `method` key, so a GET is a config object without one.
const lastGet = () => {
  const calls = axios.mock.calls.filter(
    ([conf]) => !conf.method || conf.method === "GET"
  );
  return calls[calls.length - 1][0].url;
};

const renderList = async (overrides) => {
  axios.mockResolvedValue(envelope(overrides));
  await act(async () => {
    render(
      <MemoryRouter>
        <Tenants />
      </MemoryRouter>
    );
  });
};

// Real timers throughout. lodash.debounce captures `Date.now` when it is
// imported, so Jest's fake timers move the clock the scheduler reads
// without moving the one lodash compares against, and the debounced call
// never fires. Waiting out a 400ms debounce is cheaper than that trap.
const flushDebounce = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 450));
  });

// The state filter's buttons carry the same labels as the state tags, so
// every assertion about a row's state is scoped to the table body. A bare
// getByText("Active") matches the filter control too.
const body = () => within(document.querySelector("tbody"));

describe("Tenants list", () => {
  beforeEach(() => {
    axios.mockReset();
  });

  it("renders a row per workspace with its counts", async () => {
    await renderList();
    expect(screen.getByText("mohhs")).toBeInTheDocument();
    expect(screen.getByText("Ministry of Health HSS")).toBeInTheDocument();
    expect(screen.getByText("128,430")).toBeInTheDocument();
  });

  it("shows each workspace's state", async () => {
    await renderList();
    expect(body().getByText("Active")).toBeInTheDocument();
    expect(body().getByText("Suspended")).toBeInTheDocument();
  });

  it("does not offer Inspect for a workspace that cannot resolve", async () => {
    // A suspended workspace's host 404s, so inspecting it would open a
    // dead address. The label still renders for that row — the column
    // stays legible — but only the active row's copy is a control,
    // which is the whole assertion.
    await renderList();
    expect(screen.getAllByText("Inspect")).toHaveLength(2);
    const actions = screen.getAllByRole("button", { name: "Inspect" });
    expect(actions).toHaveLength(1);
    expect(actions[0].closest("tr")).toHaveTextContent("mohhs");
  });

  it("asks the server for the chosen state instead of filtering here", async () => {
    await renderList();
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
    });
    expect(lastGet()).toContain("state=suspended");
    // Both rows are still rendered: the component shows what the server
    // sent, and the mock sent both. Asserting that "mohhs" disappeared
    // would be asserting that the browser still filters.
    expect(screen.getByText("mohhs")).toBeInTheDocument();
  });

  it("returns to the first page whenever the filter changes", async () => {
    // Enough workspaces for a second page, and standing on it, so that
    // the reset has something to undo. Rendered on page 1 the assertion
    // would hold whether or not the component resets anything.
    await renderList({ total: 60, total_page: 3 });
    await act(async () => {
      userEvent.click(screen.getByTitle("2"));
    });
    expect(lastGet()).toContain("page=2");
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
    });
    expect(lastGet()).toContain("page=1");
    expect(lastGet()).toContain("state=suspended");
  });

  it("debounces the search box into one request", async () => {
    await renderList();
    const before = axios.mock.calls.length;
    const box = screen.getByPlaceholderText("Search subdomain or name");
    await act(async () => {
      fireEvent.change(box, { target: { value: "sle" } });
      fireEvent.change(box, { target: { value: "slem" } });
      fireEvent.change(box, { target: { value: "sleman" } });
    });
    // Nothing yet: three keystrokes must not be three requests.
    expect(axios.mock.calls.length).toBe(before);
    await flushDebounce();
    expect(axios.mock.calls.length).toBe(before + 1);
    expect(lastGet()).toContain("search=sleman");
  });

  it("abandons a request that a newer filter has overtaken", async () => {
    // Two filter changes in quick succession are two requests, and
    // nothing makes the first one lose. If it lands second, the table
    // and the tiles show the suspended workspaces under an Active
    // filter -- which is the exact disagreement between the numbers and
    // the filter that this feature exists to prevent. `api.get`'s
    // cancelKey aborts the one in flight, so there is only ever one.
    await renderList();
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
    });
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Active" }));
    });
    // Every request this component issues carries an abort signal; a
    // request without one cannot be overtaken.
    const signals = axios.mock.calls.map(([conf]) => conf.signal);
    expect(signals.length).toBeGreaterThan(1);
    expect(signals.filter(Boolean)).toHaveLength(signals.length);
  });

  it("stays quiet when a request is cancelled rather than failing", async () => {
    // An aborted request is not an error an operator needs to hear
    // about. It is this component abandoning work it no longer wants.
    await renderList();
    const realIsCancel = axios.isCancel;
    axios.isCancel = jest.fn().mockReturnValue(true);
    try {
      axios.mockRejectedValueOnce(new Error("canceled"));
      await act(async () => {
        userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
      });
      expect(axios.isCancel).toHaveBeenCalled();
    } finally {
      axios.isCancel = realIsCancel;
    }
  });

  it("asks the server to sort when a column header is clicked", async () => {
    // Scoped to the header row: the tile above repeats the column's
    // label exactly, which is deliberate -- the tile row's position
    // already says "total", so "Total datapoints" over a "Datapoints"
    // column would only make a reader stop and work out which is which.
    // The cost is that a bare getByText matches both.
    await renderList();
    const header = () => within(document.querySelector("thead"));
    await act(async () => {
      userEvent.click(header().getByText("Datapoints"));
    });
    expect(lastGet()).toContain("ordering=datapoints");
    await act(async () => {
      userEvent.click(header().getByText("Datapoints"));
    });
    expect(lastGet()).toContain("ordering=-datapoints");
  });

  it("falls back to the first page when a page stops existing", async () => {
    // A workspace deleted between two requests can shrink the result
    // out from under the page an operator is standing on, and the
    // endpoint answers 404. Showing an error for a page that merely
    // stopped existing is the wrong response to an ordinary race.
    await renderList({ total: 60, total_page: 3 });
    axios.mockRejectedValueOnce({ response: { status: 404 } });
    axios.mockResolvedValue(envelope());
    await act(async () => {
      userEvent.click(screen.getByTitle("2"));
    });
    expect(lastGet()).toContain("page=1");
  });

  it("renders the totals the server sent, not the sum of the page", async () => {
    // The fixture's summary deliberately disagrees with the rows. A
    // component that added up what it had been given would show 55
    // users and 128,430 + 12,004 datapoints; the server said 900 and
    // 600,000, and the server is describing every workspace the filter
    // matched rather than these two.
    await renderList();
    const tiles = within(document.querySelector("#tenant-totals"));
    expect(tiles.getByText("900")).toBeInTheDocument();
    expect(tiles.getByText("600,000")).toBeInTheDocument();
  });

  it("takes the workspace total from the envelope, not from summary", async () => {
    // `total` is the count of workspaces matching the filter and it is
    // the only source for that number -- the pager below reads the same
    // field, so the two cannot drift.
    await renderList();
    const tiles = within(document.querySelector("#tenant-totals"));
    expect(tiles.getByText("2")).toBeInTheDocument();
  });

  it("repeats the totals under the columns that name them", async () => {
    await renderList();
    const totals = within(document.querySelector("tfoot"));
    expect(totals.getByText("600,000")).toBeInTheDocument();
    expect(totals.getByText("800")).toBeInTheDocument();
  });

  it("blanks the tiles while a filter is in flight", async () => {
    // "412" standing over a table of 28 suspended workspaces is not a
    // stale number, it is a wrong one, and it is wrong in a way an
    // operator will believe.
    await renderList();
    let resolve;
    axios.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = () => done(envelope());
        })
    );
    await act(async () => {
      userEvent.click(screen.getByRole("radio", { name: "Suspended" }));
    });
    const tiles = within(document.querySelector("#tenant-totals"));
    expect(tiles.queryByText("900")).not.toBeInTheDocument();
    await act(async () => {
      resolve();
    });
  });

  describe("the Inspect action", () => {
    const appConfig = window.appConfig;
    let originalLocation;

    beforeEach(() => {
      window.appConfig = { ...appConfig, baseDomain: "app.com" };
      originalLocation = window.location;
      delete window.location;
      window.location = {
        ...originalLocation,
        protocol: "http:",
        hostname: "admin.app.com",
        host: "admin.app.com",
        port: "",
        replace: jest.fn(),
      };
    });

    afterEach(() => {
      window.location = originalLocation;
      window.appConfig = appConfig;
    });

    it("mints a one-time code and opens the workspace with it", async () => {
      await renderList();
      // The console hands over a code, not a token, and the workspace's
      // own /inspect spends it. A bare link to that address carries no
      // credential and lands on the expired-link page.
      axios.mockResolvedValue({ status: 200, data: { code: "xyz" } });
      await act(async () => {
        userEvent.click(screen.getByRole("button", { name: "Inspect" }));
      });
      const call = axios.mock.calls.find(([conf]) => conf.method === "POST");
      expect(call[0].url).toContain("admin/tenants/1/inspect");
      expect(window.location.replace).toHaveBeenCalledWith(
        "http://mohhs.app.com/inspect?code=xyz"
      );
    });

    it("says so when the code cannot be minted", async () => {
      await renderList();
      axios.mockRejectedValue({ response: { status: 404 } });
      await act(async () => {
        userEvent.click(screen.getByRole("button", { name: "Inspect" }));
      });
      expect(window.location.replace).not.toHaveBeenCalled();
    });
  });
});
