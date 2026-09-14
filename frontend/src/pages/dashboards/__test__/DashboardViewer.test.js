import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DashboardViewer from "../DashboardViewer";
import dashboardApi from "../../../util/dashboardApi";
import { exportDashboard } from "../../../util/dashboardExport";
import { store, uiText } from "../../../lib";

jest.mock("../../../util/dashboardApi");

// The real one needs layout and a browser download; neither exists here.
jest.mock("../../../util/dashboardExport");

// The grid has its own suite; here we only care that the page hands it
// the right widgets and filters.
jest.mock("../../../components/dashboard/DashboardGrid", () => {
  const MockGrid = (props) => (
    <div
      data-testid="grid"
      data-widget-count={props.widgets.length}
      data-root-form={props.rootFormId}
      data-filters={JSON.stringify(props.filters)}
      data-dashboard-slug={props.dashboardSlug}
    />
  );
  MockGrid.displayName = "DashboardGrid";
  return MockGrid;
});

// AdministrationDropdownLocal fetches on mount; not this page's concern.
jest.mock("../../../components/dashboard/DashboardViewFilters", () => {
  const MockFilters = (props) => (
    <div
      data-testid="filters"
      data-date={String(Boolean(props.defaultFilters?.date?.enabled))}
      data-adm={String(Boolean(props.defaultFilters?.administration?.enabled))}
      data-root-adm={props.rootAdministrationId}
    />
  );
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

const PAYLOAD = {
  id: 12,
  name: "Water Points Overview",
  slug: "water-points-overview",
  description: "Operational status across all registered sites",
  root_form: { id: 6001, name: "Water Point Registration" },
  published_at: "26-08-2026 10:11:12",
  default_filters: {
    date: { enabled: true, date_question: null },
    administration: { enabled: true },
  },
  widgets: [
    { id: 1, type: "kpi", col_span: 6, title: "Operational" },
    { id: 2, type: "bar", col_span: 12, title: "By type" },
  ],
};

const setUser = (user) => {
  store.update((s) => {
    s.user = user;
    s.isLoggedIn = Boolean(user);
  });
};

const SUPERUSER = { id: 1, name: "Admin", is_superuser: true, roles: [] };

const renderViewer = (slug = "water-points-overview") =>
  render(
    <MemoryRouter initialEntries={[`/dashboards/${slug}`]}>
      <Routes>
        <Route path="/dashboards/:slug" element={<DashboardViewer />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  jest.clearAllMocks();
  setUser(SUPERUSER);
});

describe("loading a published dashboard", () => {
  test("renders name, description, filters and the grid", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());

    expect(dashboardApi.getPublished).toHaveBeenCalledWith(
      "water-points-overview"
    );
    expect(screen.getAllByText("Water Points Overview").length).toBeGreaterThan(
      0
    );
    expect(
      screen.getByText(/Operational status across all registered sites/)
    ).toBeInTheDocument();

    const grid = screen.getByTestId("grid");
    expect(grid).toHaveAttribute("data-widget-count", "2");
    // root_form arrives as {id, name}; the grid needs the bare id for the
    // escalation path segment.
    expect(grid).toHaveAttribute("data-root-form", "6001");
    // The slug from the route, passed straight through: every widget
    // request needs it so the anonymous-caller endpoints (Tasks 7, 8, 10)
    // can tell what an unauthenticated reader may ask about.
    expect(grid).toHaveAttribute(
      "data-dashboard-slug",
      "water-points-overview"
    );
  });

  test("passes default_filters and root_administration_id through to the filter bar", async () => {
    dashboardApi.getPublished.mockResolvedValue({
      data: { ...PAYLOAD, root_administration_id: 101 },
    });
    renderViewer();

    await waitFor(() =>
      expect(screen.getByTestId("filters")).toBeInTheDocument()
    );
    expect(screen.getByTestId("filters")).toHaveAttribute("data-date", "true");
    expect(screen.getByTestId("filters")).toHaveAttribute("data-adm", "true");
    expect(screen.getByTestId("filters")).toHaveAttribute(
      "data-root-adm",
      "101"
    );
  });

  test("the published viewer shows no Preview badge", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    // The mockup's view screen carries one because there, view IS preview.
    // The published viewer is not a preview of anything.
    expect(document.querySelector(".dashboard-view-badge")).toBeNull();
  });
});

describe("not found", () => {
  test.each([[404], [500]])(
    "a %s renders one not-found screen",
    async (code) => {
      dashboardApi.getPublished.mockRejectedValue({
        response: { status: code },
      });
      renderViewer();

      // Asserted against the copy itself, not a transcription of it: the
      // literal /dashboard not found/i outlived the text it was quoting
      // when #362 reworded the screen, and failed for a wording change
      // rather than for a behaviour change.
      await waitFor(() =>
        expect(
          screen.getByText(uiText.en.dashboardNotFound)
        ).toBeInTheDocument()
      );
      // Unpublished, deleted and another tenant's are indistinguishable by
      // design, so the screen does not speculate about which.
      expect(screen.queryByTestId("grid")).not.toBeInTheDocument();
    }
  );
});

describe("the top bar is a back button and nothing else", () => {
  // Edit lived here, gated on dashboard_edit. It is gone: the list already
  // offers Edit on every card, and a viewer that carries an authoring
  // control spends its widest row on chrome. The dashboard's name was
  // beside it and is dropped too — the header repeats it directly below,
  // so the bar was showing the title twice.
  test("no Edit control, for anyone", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(
      screen.queryByRole("button", { name: /edit/i })
    ).not.toBeInTheDocument();
  });

  test("back returns to wherever the visitor came from", async () => {
    // navigate(-1), not a route: #362 replaced the hardcoded hop to
    // /control-center/dashboard, which was only ever right for someone
    // who arrived from the list.
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    screen.getByRole("button", { name: /back/i }).click();
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  test("an anonymous visitor sees the back control too", async () => {
    // It used to be hidden from them because it led to
    // /control-center/dashboard, a Private route — a login wall rather
    // than a way back. Going back through history has no such problem,
    // so hiding it now would strand an anonymous visitor on the page.
    setUser(null);
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  test("a signed-in visitor sees the back control", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  test("the name is shown once, by the header", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    const { container } = renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(container.querySelector(".dashboard-view-topbar-name")).toBeNull();
    expect(screen.getAllByText(PAYLOAD.name)).toHaveLength(1);
  });
});

// ── Embedded dashboards (VIZ-019) ──

const EMBED_PAYLOAD = {
  id: 13,
  name: "Regional Sales",
  slug: "regional-sales",
  description: "Published from Power BI",
  kind: "embed",
  root_form: null,
  // A URL on the embed host, not markup: the snippet is served as its
  // own cross-origin document and never parsed in this page.
  embed_url: "http://embed.example.com/api/v1/embed/tok",
  published_at: "03-09-2026 09:00:00",
  default_filters: {},
  widgets: [],
};

describe("DashboardViewer with an embedded dashboard", () => {
  beforeEach(() => {
    dashboardApi.getPublished.mockResolvedValue({ data: EMBED_PAYLOAD });
  });

  it("renders the embed frame and not the grid", async () => {
    renderViewer("regional-sales");
    expect(await screen.findByTitle("Regional Sales")).toBeInTheDocument();
    expect(screen.queryByTestId("grid")).not.toBeInTheDocument();
  });

  it("shows no filter bar — an embed has no data of ours to filter", async () => {
    renderViewer("regional-sales");
    await screen.findByTitle("Regional Sales");
    expect(screen.queryByTestId("filters")).not.toBeInTheDocument();
  });

  it("frames the embed host URL the API supplied", async () => {
    renderViewer("regional-sales");
    const frame = await screen.findByTitle("Regional Sales");
    expect(frame).toHaveAttribute("src", EMBED_PAYLOAD.embed_url);
  });
});

describe("the content column is a flex context only for an embed", () => {
  // The wrapper's own `flex: 1 1 auto` is inert in a block container, so
  // the modifier is what actually gives the frame its height. The grid
  // shares this element and must not be relaid out to fix the embed.
  it("marks the content column on the embed branch", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: EMBED_PAYLOAD });
    const { container } = renderViewer("regional-sales");

    await screen.findByTitle("Regional Sales");
    expect(
      container.querySelector(".dashboard-view-content-embed")
    ).not.toBeNull();
  });

  it("leaves the widgets branch unmarked", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    const { container } = renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(container.querySelector(".dashboard-view-content")).not.toBeNull();
    expect(container.querySelector(".dashboard-view-content-embed")).toBeNull();
  });
});

// ── Export (VIZ-023) ──

describe("exporting the dashboard", () => {
  test("a widgets dashboard offers Export", async () => {
    // What the published endpoint actually sends: `kind` is always
    // present on the payload (dashboard_read_views.py:77).
    dashboardApi.getPublished.mockResolvedValue({
      data: { ...PAYLOAD, kind: "widgets" },
    });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });

  test("an embedded dashboard offers no Export", async () => {
    // The frame is another origin's document. Nothing in this page can
    // read into it — not html2canvas, not anything — so the capture
    // would come back as an empty box where the report should be.
    dashboardApi.getPublished.mockResolvedValue({ data: EMBED_PAYLOAD });
    renderViewer("regional-sales");

    await screen.findByTitle("Regional Sales");
    expect(
      screen.queryByRole("button", { name: /export/i })
    ).not.toBeInTheDocument();
  });

  test("a payload with no kind still offers Export", async () => {
    // The condition is `!== "embed"` rather than `=== "widgets"` on
    // purpose: it has to agree with the branch that chose to render the
    // grid, or a payload missing `kind` gets a dashboard it cannot
    // export.
    // PAYLOAD carries no `kind` at all, which is the whole point: this
    // fixture predates the field and still has to work.
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });

  test("choosing PNG exports the capture root under the dashboard name", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    const { container } = renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    userEvent.click(screen.getByRole("button", { name: /export/i }));
    userEvent.click(await screen.findByText("PNG image"));

    await waitFor(() => expect(exportDashboard).toHaveBeenCalled());
    const [node, options] = exportDashboard.mock.calls[0];
    // The capture root, not the scrolling container: capturing the
    // scroller would photograph a viewport instead of the dashboard.
    expect(node).toBe(container.querySelector(".dashboard-view-capture"));
    expect(options).toEqual({ format: "png", name: PAYLOAD.name });
  });

  test("a failed export says so instead of failing silently", async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: PAYLOAD });
    exportDashboard.mockRejectedValueOnce(new Error("tainted canvas"));
    renderViewer();

    await waitFor(() => expect(screen.getByTestId("grid")).toBeInTheDocument());
    userEvent.click(screen.getByRole("button", { name: /export/i }));
    userEvent.click(await screen.findByText("PDF document"));

    expect(await screen.findByText(/couldn't export/i)).toBeInTheDocument();
  });
});
