import React from "react";
import { render, waitFor, act } from "@testing-library/react";
import axios from "axios";
import useWidgetData from "../hooks/useWidgetData";
import { __clearVisualizationCache } from "../hooks/useVisualizationRequest";

jest.mock("axios");

// =========================================================
// What the browser still decides
// =========================================================
//
// Very little, deliberately. Choosing an endpoint, serializing escalation
// criteria and columns, and expanding `config.measure` all moved to
// `resolve_widget_data` on the server for VIZ-010, and are tested there
// (backend tests_dashboard_widget_data.py). A second copy of the measure
// rule here is precisely what VIZ-008 warned about: "one of them will
// eventually be wrong, and the number it produces will look perfectly
// reasonable."
//
// What remains is this hook's actual job: pick which of the three sources
// to ask, send only the filters a viewer may set, unwrap the envelope for
// each renderer, and own the table's page.

const SLUG = "water-points";
const DASHBOARD_ID = 12;

const NO_FILTERS = {
  from_date: null,
  to_date: null,
  date_question_id: null,
  administration_id: null,
};

const ALL_FILTERS = {
  from_date: "2026-01-01",
  to_date: "2026-07-31",
  date_question_id: 600204,
  administration_id: 42,
};

// @testing-library/react is pinned at ^12, which has no renderHook.
const HookProbe = ({ run, onResult }) => {
  onResult(run());
  return null;
};

const mount = (run) => {
  let latest;
  const utils = render(
    <HookProbe
      run={run}
      onResult={(r) => {
        latest = r;
      }}
    />
  );
  return { latest: () => latest, ...utils };
};

const widget = (overrides = {}) => ({
  id: 7,
  type: "kpi",
  title: "Operational",
  color: "#64A73B",
  form: 6002,
  question: 600203,
  config: { measure: "current_state" },
  ...overrides,
});

const run = (w, filters = NO_FILTERS, options = { slug: SLUG }) =>
  mount(() => useWidgetData(w, filters, options));

const settle = async (probe) =>
  waitFor(() => expect(probe.latest().loading).toBe(false));

const call = () => axios.mock.calls[0]?.[0];

beforeEach(() => {
  axios.mockReset();
  __clearVisualizationCache();
});

// ── which source ─────────────────────────────────────────────────────

describe("source selection", () => {
  test("a saved widget is fetched by id", async () => {
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget());
    await settle(probe);

    expect(call().url).toBe(`dashboards/${SLUG}/widgets/7/data`);
  });

  test("the public flag changes only the namespace", async () => {
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget(), NO_FILTERS, {
      slug: SLUG,
      isPublic: true,
    });
    await settle(probe);

    expect(call().url).toBe(`public/dashboards/${SLUG}/widgets/7/data`);
  });

  test("an unsaved widget is posted for preview", async () => {
    // The canvas renders unsaved state, and a widget added a moment ago
    // has no id to address. Builder temp ids are negative.
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const unsaved = widget({ id: -1 });
    const probe = run(unsaved, NO_FILTERS, {
      slug: SLUG,
      dashboardId: DASHBOARD_ID,
    });
    await settle(probe);

    expect(call().url).toBe(`manage/dashboards/${DASHBOARD_ID}/preview-widget`);
    expect(call().data.widget).toEqual(unsaved);
  });

  test("an unsaved widget is never posted to the public namespace", async () => {
    // There is no anonymous way to author a widget, and offering one
    // would put a widget config back on the public wire.
    const probe = run(widget({ id: -1 }), NO_FILTERS, {
      slug: SLUG,
      isPublic: true,
      dashboardId: DASHBOARD_ID,
    });
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });

  test("an unsaved widget with no dashboard yet asks for nothing", async () => {
    const probe = run(widget({ id: -1 }), NO_FILTERS, { slug: SLUG });
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });

  test.each([
    ["a section title", { type: "section_title", config: { text: "Hi" } }],
    ["a broken widget", { is_broken: true }],
  ])("%s issues no request", async (_label, overrides) => {
    const probe = run(widget(overrides));
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });
});

// ── what travels ─────────────────────────────────────────────────────

describe("only the viewer's own filters are sent", () => {
  test("all four reach the request", async () => {
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget(), ALL_FILTERS);
    await settle(probe);

    expect(call().params).toEqual({
      from_date: "2026-01-01",
      to_date: "2026-07-31",
      date_question_id: 600204,
      administration_id: 42,
      page: 1,
    });
  });

  test("nothing about the widget itself is sent", async () => {
    // The whole point of VIZ-010 D-3: no form_id, no question_id, no
    // query grammar. The server reads all of that from the widget.
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget({ type: "bar", config: { group_by: "option" } }));
    await settle(probe);

    const sent = Object.keys(call().params);
    ["form_id", "question_id", "monitoring", "sum_by", "group_by"].forEach(
      (key) => expect(sent).not.toContain(key)
    );
  });

  test("unset filters are omitted rather than sent empty", async () => {
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget());
    await settle(probe);
    expect(call().params).toEqual({ page: 1 });
  });
});

// ── unwrapping ───────────────────────────────────────────────────────

describe("normalization to the renderers' input contract", () => {
  const resolve = async (type, payload, config = {}) => {
    axios.mockResolvedValue({ data: { data: payload } });
    const probe = run(widget({ type, config }));
    await settle(probe);
    return probe.latest();
  };

  test("kpi unwraps to a single value", async () => {
    const out = await resolve("kpi", {
      data: [{ value: 42, label: "Total" }],
    });
    expect(out.data).toEqual({ value: 42 });
  });

  test("kpi with no rows yields null rather than throwing", async () => {
    const out = await resolve("kpi", { data: [] });
    expect(out.data).toEqual({ value: null });
  });

  test("chart rows keep only label and value", async () => {
    // akvo-charts derives its series from the object's keys, so `group`
    // or `color` would each be plotted as an extra series.
    const out = await resolve("bar", {
      data: [{ label: "A", value: 1, group: "a", color: "#fff" }],
    });
    expect(out.data).toEqual([{ label: "A", value: 1 }]);
  });

  test("group_by=option lifts per-option colours onto renderWidget", async () => {
    const out = await resolve(
      "pie",
      { data: [{ label: "A", value: 1, color: "#64A73B" }] },
      { group_by: "option" }
    );
    expect(out.renderWidget.color).toEqual(["#64A73B"]);
  });

  test("stack_by passes rows through unprojected", async () => {
    const out = await resolve(
      "bar",
      { data: [{ label: "Jan", a: 1, b: 2 }], stack_labels: ["a", "b"] },
      { stack_by: "option" }
    );
    expect(out.data).toEqual([{ label: "Jan", a: 1, b: 2 }]);
    expect(out.renderWidget.config.stackMapping).toEqual({
      stack: ["a", "b"],
    });
  });

  test("table unwraps results and reports the whole set's size", async () => {
    const out = await resolve("table", {
      count: 5,
      results: [{ id: 1 }, { id: 2 }, { id: 3 }],
    });
    expect(out.data).toHaveLength(3);
    expect(out.pagination.total).toBe(5);
  });

  test("map passes its points through", async () => {
    const out = await resolve("map", [
      { id: 1, name: "A", geo: [1, 2], status: "active" },
    ]);
    expect(out.data[0].status).toBe("active");
  });
});

// ── paging ───────────────────────────────────────────────────────────

describe("table pagination", () => {
  const table = () =>
    widget({ type: "table", question: null, config: { page_size: 3 } });

  test("it reports the page it holds and the size of the set", async () => {
    axios.mockResolvedValue({
      data: { data: { count: 5, results: [{ id: 1 }] } },
    });
    const probe = run(table());
    await settle(probe);

    expect(probe.latest().pagination).toMatchObject({
      total: 5,
      current: 1,
      pageSize: 3,
    });
  });

  test("asking for another page re-requests it", async () => {
    axios.mockResolvedValue({ data: { data: { count: 5, results: [] } } });
    const probe = run(table());
    await settle(probe);

    await act(async () => {
      probe.latest().pagination.onChange(2);
    });
    await settle(probe);

    const pages = axios.mock.calls.map((c) => c[0].params.page);
    expect(pages).toContain(2);
    expect(probe.latest().pagination.current).toBe(2);
  });

  test("a chart reports no pagination at all", async () => {
    axios.mockResolvedValue({ data: { data: { data: [] } } });
    const probe = run(widget({ type: "bar" }));
    await settle(probe);
    expect(probe.latest().pagination).toBeNull();
  });
});

// ── failure ──────────────────────────────────────────────────────────

describe("failure containment", () => {
  test("a rejected request sets error and leaves data null", async () => {
    axios.mockRejectedValue(new Error("boom"));
    const probe = run(widget());
    await settle(probe);

    expect(probe.latest().data).toBeNull();
    expect(probe.latest().error).toBeTruthy();
  });
});
