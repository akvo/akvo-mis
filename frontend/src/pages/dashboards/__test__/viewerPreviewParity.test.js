import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DashboardViewer from "../DashboardViewer";
import DashboardBuilder from "../DashboardBuilder";
import dashboardApi from "../../../util/dashboardApi";
import useWidgetData from "../../../util/hooks/useWidgetData";
import { store } from "../../../lib";

jest.mock("../../../util/dashboardApi");
jest.mock("../../../util/hooks/useWidgetData");

// The filter bar fetches administrations on mount and is identical on both
// paths; stubbing it keeps this test about the grid.
jest.mock("../../../components/dashboard/DashboardViewFilters", () => {
  const MockFilters = () => <div data-testid="filters" />;
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});

jest.mock("akvo-charts", () => ({
  Bar: ({ config }) => (
    <div data-testid="chart-bar" data-color={JSON.stringify(config?.color)} />
  ),
  StackBar: () => <div data-testid="chart-stackbar" />,
  Line: () => <div data-testid="chart-line" />,
  StackLine: () => <div data-testid="chart-stackline" />,
  Pie: ({ config }) => (
    <div data-testid="chart-pie" data-color={JSON.stringify(config?.color)} />
  ),
  Doughnut: () => <div data-testid="chart-doughnut" />,
  MapCluster: () => <div data-testid="chart-map" />,
}));

const ROOT_FORM = { id: 6001, name: "Registration" };

// Deliberately no `is_broken` key. The viewer's payload is annotated by
// the server and the builder's local state is not — but the builder cannot
// save a broken widget in the first place (VIZ-007 D-4), so in preview the
// flag is always absent and would always have been false. That is the one
// asymmetry between the two inputs, and it is intentional.
const WIDGETS = [
  {
    id: 1,
    type: "section_title",
    col_span: 24,
    title: "Current status",
    config: { text: "Current status" },
  },
  {
    id: 2,
    type: "kpi",
    col_span: 6,
    title: "Operational",
    color: "#64A73B",
    form: 6002,
    question: 600203,
    config: { measure: "current_state", value_type: "number" },
  },
  {
    id: 3,
    type: "bar",
    col_span: 12,
    title: "By source type",
    color: "#1890ff",
    form: 6002,
    question: 600203,
    config: { measure: "current_state", group_by: "option" },
  },
  {
    id: 4,
    type: "pie",
    col_span: 8,
    title: "Share",
    color: "#1651b6",
    form: 6002,
    question: 600203,
    config: { measure: "current_state", group_by: "option", variant: "pie" },
  },
];

const DATA_FOR = {
  kpi: { value: 12480 },
  bar: [
    { label: "Borehole", value: 42 },
    { label: "Spring", value: 28 },
  ],
  pie: [
    { label: "Operational", value: 55 },
    { label: "Issue", value: 25 },
  ],
};

const DASHBOARD = {
  id: 12,
  name: "Water Points Overview",
  slug: "water-points-overview",
  description: "Operational status across all registered sites",
  status: "published",
  root_form: ROOT_FORM,
  default_filters: {
    date: { enabled: true },
    administration: { enabled: true },
  },
  widgets: WIDGETS,
};

const gridHtml = () => document.querySelector(".dashboard-view-grid").innerHTML;

beforeEach(() => {
  jest.clearAllMocks();
  store.update((s) => {
    s.user = { id: 1, name: "Admin", is_superuser: true, roles: [] };
  });
  useWidgetData.mockImplementation((widget) => ({
    data: DATA_FOR[widget.type] ?? null,
    renderWidget: widget,
    pagination: null,
    loading: false,
    error: null,
    refetch: jest.fn(),
  }));
});

const renderViewer = async () => {
  dashboardApi.getPublished.mockResolvedValue({ data: DASHBOARD });
  const utils = render(
    <MemoryRouter initialEntries={["/dashboards/water-points-overview"]}>
      <Routes>
        <Route path="/dashboards/:slug" element={<DashboardViewer />} />
      </Routes>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(document.querySelector(".dashboard-view-grid")).toBeInTheDocument()
  );
  return utils;
};

const renderBuilderPreview = async () => {
  dashboardApi.list.mockResolvedValue({ data: [DASHBOARD] });
  dashboardApi.get.mockResolvedValue({ data: DASHBOARD });
  dashboardApi.sources.mockResolvedValue({ data: { forms: [] } });

  const utils = render(
    <MemoryRouter
      initialEntries={["/control-center/dashboard/water-points-overview"]}
    >
      <Routes>
        <Route
          path="/control-center/dashboard/:slug"
          element={<DashboardBuilder />}
        />
      </Routes>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /preview/i })).toBeInTheDocument()
  );
  fireEvent.click(screen.getByRole("button", { name: /preview/i }));
  await waitFor(() =>
    expect(document.querySelector(".dashboard-view-grid")).toBeInTheDocument()
  );
  return utils;
};

describe("viewer and preview are the same renderer", () => {
  test("the same widget array produces identical grid markup", async () => {
    const viewer = await renderViewer();
    const viewerHtml = gridHtml();
    viewer.unmount();

    const preview = await renderBuilderPreview();
    const previewHtml = gridHtml();
    preview.unmount();

    expect(previewHtml).toBe(viewerHtml);
  });

  test("both render every widget", async () => {
    await renderViewer();
    expect(screen.getByTestId("chart-bar")).toBeInTheDocument();
    expect(screen.getByTestId("chart-pie")).toBeInTheDocument();
    expect(screen.getByText("12,480")).toBeInTheDocument();
    expect(screen.getByText("Current status")).toBeInTheDocument();
  });
});

// ── Embedded dashboards (VIZ-019) ──
//
// Spec D-9 makes Preview the entire mitigation for an embed whose failure
// to load we cannot detect: the author is told to check it there because
// "Preview renders the frame exactly as the viewer will". That promise is
// carried by one class. `.dashboard-view-content` is `flex: 1;
// overflow-y: auto` with no `display: flex`, so without the -embed
// modifier `.dashboard-embed-frame { flex: 1 1 auto }` never applies and
// the frame sits at its 480px min-height while the published page fills
// the column. Same class on both sides, or the author is sizing their
// vendor report against a page nobody else sees.

const EMBED = {
  id: 13,
  name: "Regional Sales",
  slug: "regional-sales",
  description: "Published from Power BI",
  kind: "embed",
  root_form: null,
  embed_snippet: "<iframe src='https://app.powerbi.com/view?r=1'></iframe>",
  embed_url: "http://embed.example.com/api/v1/embed/tok",
  status: "published",
  is_public: true,
  default_filters: {},
  widgets: [],
};

const contentClass = () =>
  document.querySelector(".dashboard-view-content").className;

describe("an embed previews at the height it publishes at", () => {
  const renderEmbedViewer = async () => {
    dashboardApi.getPublished.mockResolvedValue({ data: EMBED });
    const utils = render(
      <MemoryRouter initialEntries={["/dashboards/regional-sales"]}>
        <Routes>
          <Route path="/dashboards/:slug" element={<DashboardViewer />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByTitle(EMBED.name);
    return utils;
  };

  const renderEmbedPreview = async () => {
    dashboardApi.list.mockResolvedValue({ data: [EMBED] });
    dashboardApi.get.mockResolvedValue({ data: EMBED });
    // Preview mints its own URL; parity here is about the column the
    // frame sits in, not about which token the URL carries.
    dashboardApi.embedPreview.mockResolvedValue({
      data: { embed_url: EMBED.embed_url },
    });
    const utils = render(
      <MemoryRouter
        initialEntries={["/control-center/dashboard/regional-sales"]}
      >
        <Routes>
          <Route
            path="/control-center/dashboard/:slug"
            element={<DashboardBuilder />}
          />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /preview/i })
      ).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    await screen.findByTitle(EMBED.name);
    return utils;
  };

  test("both give the content column the same class", async () => {
    const viewer = await renderEmbedViewer();
    const viewerClass = contentClass();
    viewer.unmount();

    const preview = await renderEmbedPreview();
    const previewClass = contentClass();
    preview.unmount();

    expect(previewClass).toBe(viewerClass);
    expect(previewClass).toContain("dashboard-view-content-embed");
  });
});

describe("preview is a mode, not a new tab", () => {
  test("it hides the palette and the inspector, and restores them", async () => {
    const openSpy = jest.spyOn(window, "open").mockImplementation(() => null);
    await renderBuilderPreview();

    expect(document.querySelector(".builder-palette")).toBeNull();
    expect(document.querySelector(".builder-canvas")).toBeNull();
    // The old behaviour: window.open("/dashboards/" + slug), which showed
    // the last published snapshot rather than unsaved work.
    expect(openSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /back to editing/i }));
    await waitFor(() =>
      expect(document.querySelector(".builder-canvas")).toBeInTheDocument()
    );
    expect(document.querySelector(".dashboard-view-grid")).toBeNull();
    openSpy.mockRestore();
  });

  test("the preview badge appears only while previewing", async () => {
    await renderBuilderPreview();
    expect(document.querySelector(".dashboard-view-badge")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /back to editing/i }));
    await waitFor(() =>
      expect(document.querySelector(".dashboard-view-badge")).toBeNull()
    );
  });

  test("Save and Publish stay reachable while previewing", async () => {
    await renderBuilderPreview();
    expect(
      screen.getByRole("button", { name: /save dashboard/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /publish/i })
    ).toBeInTheDocument();
  });
});
