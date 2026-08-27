import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DashboardBuilder from "../DashboardBuilder";
import dashboardApi from "../../../util/dashboardApi";
import useWidgetData from "../../../util/hooks/useWidgetData";
import { store } from "../../../lib";

jest.mock("../../../util/dashboardApi");
jest.mock("../../../util/hooks/useWidgetData");

jest.mock("../../../components/dashboard/DashboardViewFilters", () => {
  const MockFilters = () => <div data-testid="filters" />;
  MockFilters.displayName = "DashboardViewFilters";
  return MockFilters;
});

jest.mock("akvo-charts", () => ({
  Bar: () => <div data-testid="chart-bar" />,
  StackBar: () => <div data-testid="chart-stackbar" />,
  Line: () => <div data-testid="chart-line" />,
  StackLine: () => <div data-testid="chart-stackline" />,
  Pie: () => <div data-testid="chart-pie" />,
  Doughnut: () => <div data-testid="chart-doughnut" />,
  MapCluster: () => <div data-testid="chart-map" />,
}));

// =========================================================
// A new widget must be savable without being reconfigured
// =========================================================
//
// `measure: current_state` means "the latest submission per site", which
// is only defined relative to a monitoring form — validate_dashboard_payload
// rejects it on a registration form with "measure current_state requires a
// monitoring form" (dashboard_functions.py:333).
//
// /sources returns the root registration form FIRST and its monitoring
// children after it (serialize_sources), so `forms[0]` — what a new widget
// is bound to — is always a registration form. A default measure of
// current_state therefore made every freshly added chart widget unsavable
// until the author manually re-pointed it at a monitoring form.

const ROOT_FORM = { id: 6001, name: "Registration", type: "registration" };
const MONITORING_FORM = { id: 6002, name: "Monitoring", type: "monitoring" };

const SOURCES = {
  forms: [
    { ...ROOT_FORM, questions: [{ id: 600101, name: "Site type" }] },
    { ...MONITORING_FORM, questions: [{ id: 600203, name: "Status" }] },
  ],
};

const DASHBOARD = {
  id: 12,
  name: "Water Points Overview",
  slug: "water-points-overview",
  description: "",
  status: "draft",
  root_form: ROOT_FORM,
  default_filters: {
    date: { enabled: true },
    administration: { enabled: true },
  },
  widgets: [],
};

const renderBuilder = async (sources = SOURCES) => {
  dashboardApi.list.mockResolvedValue({ data: [DASHBOARD] });
  dashboardApi.get.mockResolvedValue({ data: DASHBOARD });
  dashboardApi.sources.mockResolvedValue({ data: sources });
  dashboardApi.update.mockResolvedValue({ data: DASHBOARD });

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
  return utils;
};

const addWidget = (label) =>
  fireEvent.click(screen.getByText(label).closest("button"));

const save = async () => {
  fireEvent.click(screen.getByRole("button", { name: /save/i }));
  await waitFor(() => expect(dashboardApi.update).toHaveBeenCalled());
  return dashboardApi.update.mock.calls[0][1];
};

beforeEach(() => {
  jest.clearAllMocks();
  store.update((s) => {
    s.user = { id: 1, name: "Admin", is_superuser: true, roles: [] };
  });
  useWidgetData.mockImplementation((widget) => ({
    data: null,
    renderWidget: widget,
    pagination: null,
    loading: false,
    error: null,
    refetch: jest.fn(),
  }));
});

describe("a new widget defaults to a measure its form supports", () => {
  test.each([
    ["Bar chart", "bar"],
    ["Line chart", "line"],
    ["Pie / doughnut", "pie"],
    ["KPI card", "kpi"],
  ])(
    "%s bound to the registration form carries no current_state",
    async (label, type) => {
      await renderBuilder();
      addWidget(label);
      const payload = await save();

      const widget = payload.widgets.find((w) => w.type === type);
      expect(widget.form).toBe(ROOT_FORM.id);
      // The rejection the author actually saw. Anything but current_state
      // is fine here — absent and null both pass the server's `is not None`
      // guard.
      expect(widget.config.measure).not.toBe("current_state");
    }
  );

  test("a monitoring-only family still defaults to current_state", async () => {
    // When /sources leads with a monitoring form the default is not merely
    // allowed, it is the right one — VIZ-006 D-4 makes current_state the
    // default on any monitoring-form widget.
    await renderBuilder({
      forms: [{ ...MONITORING_FORM, questions: [] }],
    });
    addWidget("Bar chart");
    const payload = await save();

    expect(payload.widgets[0].form).toBe(MONITORING_FORM.id);
    expect(payload.widgets[0].config.measure).toBe("current_state");
  });

  test("a section title is never given a measure", async () => {
    await renderBuilder();
    addWidget("Section title");
    const payload = await save();

    expect(payload.widgets[0].config.measure).toBeFalsy();
  });
});
