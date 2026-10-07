import React from "react";
import { render, act } from "@testing-library/react";
import useWidgetData from "../hooks/useWidgetData";
import useVisualizationRequest from "../hooks/useVisualizationRequest";

jest.mock("../hooks/useVisualizationRequest");

// VIZ-027 §7: every request of every widget type carries global_criteria.
// The endpoints silently drop a parameter they do not know, so a builder
// that forgets it does not fail; it shows unfiltered data. Hence one row
// per request a widget can make.

// The backend fixture's forms (global_filter_mixin.py).
const ROOT = 7001; // Water point registration
const MONITORING = 7002; // Water quality visit
const SLUG = "water-points";
// "Is the infrastructure operational?" -> show only Operational. An
// array, one entry per value (D-15), by form and name (D-20, D-21).
const GLOBAL = ["option_in:7003:infrastructure_status:operational"];

const WIDGETS = {
  // 700201 "Were you able to take a water sample?" Yes | No
  // 700202 "How many households use this water point?" (number)
  // 700101 "What is the water source?" (registration)
  kpi: { id: 1, type: "kpi", form: MONITORING, question: 700201, config: {} },
  bar: {
    id: 2,
    type: "bar",
    form: MONITORING,
    question: 700201,
    config: { group_by: "option" },
  },
  pie: {
    id: 3,
    type: "pie",
    form: MONITORING,
    question: 700201,
    config: { group_by: "option" },
  },
  line: {
    id: 4,
    type: "line",
    form: MONITORING,
    question: 700202,
    config: { group_by: "month" },
  },
  scatter: {
    id: 5,
    type: "scatter",
    form: MONITORING,
    question: 700202,
    config: { question_y: 700202 },
  },
  table: {
    id: 6,
    type: "table",
    form: MONITORING,
    question: null,
    config: { columns: [{ key: "name", source: "parent_name" }] },
  },
  "map + status colours": {
    id: 7,
    type: "map",
    form: MONITORING,
    question: 700201,
    config: { status_colors: { yes: "#00f", no: "#f00" } },
  },
  "map + value question": {
    id: 8,
    type: "map",
    form: MONITORING,
    question: 700202,
    config: { map_mode: "quantity" },
  },
  "bar stacked across forms": {
    id: 9,
    type: "bar",
    form: MONITORING,
    question: 700201,
    config: {
      group_by: "parent_id",
      stack_by: "option",
      stack_form: ROOT,
      stack_question: 700101,
    },
  },
};

// How many requests each widget is expected to make, so a builder that
// returns null by mistake fails here rather than passing vacuously.
const EXPECTED_REQUESTS = {
  kpi: 1,
  bar: 1,
  pie: 1,
  line: 1,
  scatter: 1,
  table: 1,
  "map + status colours": 2,
  "map + value question": 2,
  "bar stacked across forms": 2,
};

const Probe = ({ widget, filters }) => {
  useWidgetData(widget, filters, { rootFormId: ROOT, dashboardSlug: SLUG });
  return null;
};

const requestsFor = (widget, filters) => {
  useVisualizationRequest.mockClear();
  render(<Probe widget={widget} filters={filters} />);
  return useVisualizationRequest.mock.calls
    .filter(([endpoint]) => endpoint)
    .map(([endpoint, params]) => ({ endpoint, params }));
};

beforeEach(() => {
  useVisualizationRequest.mockReturnValue({
    data: null,
    loading: false,
    error: null,
    refetch: jest.fn(),
  });
});

describe.each(Object.entries(WIDGETS))("%s", (name, widget) => {
  test("makes the requests this table expects", () => {
    const endpoints = new Set(
      requestsFor(widget, { global_criteria: GLOBAL }).map(
        (r) => `${r.endpoint} ${JSON.stringify(r.params)}`
      )
    );
    expect(endpoints.size).toBe(EXPECTED_REQUESTS[name]);
  });

  test("every request carries global_criteria", () => {
    const requests = requestsFor(widget, { global_criteria: GLOBAL });
    requests.forEach(({ endpoint, params }) => {
      expect({ endpoint, value: params.global_criteria }).toEqual({
        endpoint,
        value: GLOBAL,
      });
    });
  });

  test("no request names it when no filter is set", () => {
    const requests = requestsFor(widget, { global_criteria: null });
    requests.forEach(({ params }) => {
      expect(params).not.toHaveProperty("global_criteria");
    });
  });

  test("every request carries global_match when it is any (D-21)", () => {
    const requests = requestsFor(widget, {
      global_criteria: GLOBAL,
      global_match: "any",
    });
    requests.forEach(({ endpoint, params }) => {
      expect({ endpoint, value: params.global_match }).toEqual({
        endpoint,
        value: "any",
      });
    });
  });

  test("no request names global_match when it is unset", () => {
    const requests = requestsFor(widget, {
      global_criteria: GLOBAL,
      global_match: null,
    });
    requests.forEach(({ params }) => {
      expect(params).not.toHaveProperty("global_match");
    });
  });
});

// D-18: the dashboard's date question dates map pins, colours and sizes
// too; the backend matches it by name on each form.
test.each(["map + status colours", "map + value question"])(
  "%s: every request carries date_question_id",
  (name) => {
    const requests = requestsFor(WIDGETS[name], {
      from_date: "2025-01-01",
      date_question_id: 700203,
    });
    expect(requests.length).toBe(EXPECTED_REQUESTS[name]);
    requests.forEach(({ endpoint, params }) => {
      expect({ endpoint, value: params.date_question_id }).toEqual({
        endpoint,
        value: 700203,
      });
    });
  }
);

test("the cross-form series request names the public dashboard (A7)", () => {
  const requests = requestsFor(WIDGETS["bar stacked across forms"], {});
  const series = requests.find((r) => r.params.form_id === ROOT);
  expect(series.params.dashboard_slug).toBe(SLUG);
  expect(series.params).not.toHaveProperty("dashboard");
});

// Like the WAI portal (parent §15): a table on page 3 goes back to page 1
// when the filter changes, or the filtered set may end before page 3 and
// the backend answers with an empty page. Green today; a guard.
test("a filter change sends the table back to page 1", () => {
  useVisualizationRequest.mockReturnValue({
    data: { count: 100, results: [] },
    loading: false,
    error: null,
    refetch: jest.fn(),
  });
  const NO_FILTER = {};
  let latest = null;
  const TableProbe = ({ filters }) => {
    latest = useWidgetData(WIDGETS.table, filters, {
      rootFormId: ROOT,
      dashboardSlug: SLUG,
    });
    return null;
  };
  const lastTablePage = () =>
    useVisualizationRequest.mock.calls
      .filter(([endpoint]) => endpoint?.startsWith("visualization/escalation"))
      .pop()[1].page;

  const { rerender } = render(<TableProbe filters={NO_FILTER} />);
  act(() => latest.pagination.onChange(3));
  expect(lastTablePage()).toBe(3);

  rerender(<TableProbe filters={{ global_criteria: GLOBAL }} />);
  expect(lastTablePage()).toBe(1);
});
