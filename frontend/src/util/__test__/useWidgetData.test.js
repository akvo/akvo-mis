import React from "react";
import { render, waitFor, act } from "@testing-library/react";
import axios from "axios";
import useWidgetData from "../hooks/useWidgetData";
import { __clearVisualizationCache } from "../hooks/useVisualizationRequest";

jest.mock("axios");

// Seeded fixture ids (form_seeder --test, example-vis-6).
const ROOT = 6001;
const MONITORING = 6002;
const QUESTION = 600203;

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

// The house harness (see dashboardHooks.test.js): @testing-library/react is
// pinned at ^12, which has no renderHook.
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
  id: 1,
  type: "kpi",
  title: "Operational",
  color: "#64A73B",
  form: MONITORING,
  question: QUESTION,
  config: { measure: "current_state" },
  ...overrides,
});

const run = (w, filters = NO_FILTERS) =>
  mount(() => useWidgetData(w, filters, { rootFormId: ROOT }));

const callFor = (urlFragment) =>
  axios.mock.calls
    .map((c) => c[0])
    .find((c) => c.url && c.url.includes(urlFragment));

const settle = async (probe) =>
  waitFor(() => expect(probe.latest().loading).toBe(false));

beforeEach(() => {
  axios.mockReset();
  __clearVisualizationCache();
});

// ── Endpoint and parameter selection ─────────────────────────────────

describe("endpoint selection", () => {
  test("kpi requests /values with the expanded measure", async () => {
    axios.mockResolvedValue({
      data: { data: [{ value: 42, label: "Total" }], labels: ["Total"] },
    });

    const probe = run(widget());
    await settle(probe);

    expect(axios).toHaveBeenCalledTimes(1);
    const call = axios.mock.calls[0][0];
    expect(call.url).toBe("visualization/values");
    expect(call.params).toEqual({
      form_id: MONITORING,
      question_id: QUESTION,
      monitoring: "latest",
      sum_by: "parent_id",
    });
  });

  test("bar forwards group_by, stack_by, value_type and repeat_agg", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });

    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "month",
          stack_by: "option",
          value_type: "percentage",
          repeat_agg: "sum",
          orientation: "horizontal",
        },
      })
    );
    await settle(probe);

    const { params } = axios.mock.calls[0][0];
    expect(params).toEqual({
      form_id: MONITORING,
      question_id: QUESTION,
      monitoring: "all",
      group_by: "month",
      stack_by: "option",
      value_type: "percentage",
      repeat_agg: "sum",
    });
    // Presentation only — VIZ-001 §4.3 says orientation never reaches the
    // backend, and sending it would fork the request cache key for free.
    expect(params).not.toHaveProperty("orientation");
  });

  test("pie forwards option_value", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });

    const probe = run(
      widget({
        type: "pie",
        config: {
          measure: "current_state",
          group_by: "option",
          option_value: "operational",
          variant: "doughnut",
        },
      })
    );
    await settle(probe);

    const { params } = axios.mock.calls[0][0];
    expect(params.option_value).toBe("operational");
    expect(params).not.toHaveProperty("variant");
  });

  test("table requests /escalation on the ROOT form, widget form as monitoring", async () => {
    axios.mockResolvedValue({ data: { count: 0, results: [] } });

    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
            { type: "threshold_gt", question: 600205, value: 5 },
          ],
          columns: [
            { key: "site", source: "parent_name" },
            { key: "location", source: "administration" },
            { key: "status", source: "answer", question: QUESTION },
            { key: "checked", source: "latest_date", question: 600206 },
          ],
          page_size: 25,
        },
      })
    );
    await settle(probe);

    const call = axios.mock.calls[0][0];
    // The path form is the registration parent; the widget's own form is
    // the monitoring child. Escalation is inherently a "parent plus its
    // latest monitoring child" query.
    expect(call.url).toBe(`visualization/escalation/${ROOT}`);
    expect(call.params.monitoring_form_id).toBe(MONITORING);
    expect(call.params.criteria).toBe(
      `option_equals:${QUESTION}:issue,threshold_gt:600205:5`
    );
    expect(call.params.columns).toBe(
      `site:parent_name,location:administration,status:answer:${QUESTION},checked:latest_date:600206`
    );
    expect(call.params.page_size).toBe(25);
  });

  test("map requests geolocation on the REGISTRATION form", async () => {
    axios.mockResolvedValue({ data: [] });

    const probe = run(widget({ type: "map", config: {} }));
    await settle(probe);

    const call = callFor("maps/geolocation");
    // Not the widget's own form. `geo` is captured at registration;
    // monitoring rows carry none, so asking the monitoring form returns an
    // empty list forever. The widget's form is the colour source and goes
    // out as monitoring_form_id instead.
    expect(call.url).toBe(`maps/geolocation/${ROOT}`);
    expect(call.url).not.toContain(String(MONITORING));
  });

  test("section_title issues no request", async () => {
    const probe = run(
      widget({
        type: "section_title",
        form: null,
        question: null,
        config: { text: "Hi" },
      })
    );
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });

  test("a broken widget issues no request", async () => {
    const probe = run(
      widget({ is_broken: true, broken_reason: "question_deleted" })
    );
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });

  // form_id is `required=True` on ValuesFilterSerializer, so a widget that
  // has not been given a data source yet is a guaranteed 400 — re-issued
  // on every keystroke once the builder canvas fetches, and rendered as a
  // network error for what is really an unfinished widget. question_id is
  // NOT part of this: it is optional, and a count-only KPI legitimately
  // has none.
  test.each(["kpi", "bar", "line", "pie"])(
    "a %s with no data source issues no request",
    async (type) => {
      const probe = run(widget({ type, form: null, question: null }));
      await settle(probe);
      expect(axios).not.toHaveBeenCalled();
    }
  );

  test("a count-only KPI still requests without a question", async () => {
    axios.mockResolvedValue({ data: { data: [{ label: "Total", value: 5 }] } });
    const probe = run(widget({ question: null }));
    await settle(probe);
    const call = callFor("visualization/values");
    expect(call.params.form_id).toBe(MONITORING);
    expect(call.params.question_id).toBeUndefined();
  });
});

describe("entries the backend would reject are dropped, not sent", () => {
  test("a latest_date column with no question id is skipped", async () => {
    axios.mockResolvedValue({ data: { count: 0, results: [] } });
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
          ],
          columns: [
            { key: "site", source: "parent_name" },
            // What the inspector's "Last submission" checkbox actually
            // writes. validate_columns() refuses it, and the 400 would
            // take the whole table with it.
            { key: "latest_date", source: "latest_date" },
          ],
        },
      })
    );
    await settle(probe);

    expect(axios.mock.calls[0][0].params.columns).toBe("site:parent_name");
  });

  test("a half-filled criterion row is skipped", async () => {
    axios.mockResolvedValue({ data: { count: 0, results: [] } });
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
            // The inspector seeds this the moment "Add criterion" is
            // clicked, before the author picks a question.
            { type: "option_equals", question: null, value: "" },
          ],
          columns: [{ key: "site", source: "parent_name" }],
        },
      })
    );
    await settle(probe);

    expect(axios.mock.calls[0][0].params.criteria).toBe(
      `option_equals:${QUESTION}:issue`
    );
  });

  test("a table whose every column is unusable issues no request", async () => {
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
          ],
          columns: [{ key: "latest_date", source: "latest_date" }],
        },
      })
    );
    await settle(probe);
    expect(axios).not.toHaveBeenCalled();
  });
});

describe("a table that cannot be requested is not requested", () => {
  test.each([
    [
      "empty columns",
      {
        criteria: [{ type: "option_equals", question: 1, value: "x" }],
        columns: [],
      },
    ],
    ["neither columns nor criteria", {}],
  ])("%s", async (_label, config) => {
    const probe = run(widget({ type: "table", question: null, config }));
    await settle(probe);
    // Columns are what the request asks for and what the grid draws, and
    // /escalation still marks them required — without them this would be a
    // guaranteed 400 re-issued on every filter change.
    expect(axios).not.toHaveBeenCalled();
  });

  test("no criteria is a request for every datapoint, not a broken one", async () => {
    axios.mockResolvedValue({ data: { count: 0, results: [] } });
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [],
          columns: [{ key: "site", source: "parent_name" }],
        },
      })
    );
    await settle(probe);

    const call = callFor("visualization/escalation");
    expect(call).toBeDefined();
    // Nothing to narrow by, so the parameter is left off entirely rather
    // than sent empty.
    expect(call.params).not.toHaveProperty("criteria");
  });
});

describe("filter merge", () => {
  test("/values takes all four parameters", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(widget(), ALL_FILTERS);
    await settle(probe);

    const { params } = axios.mock.calls[0][0];
    expect(params.from_date).toBe("2026-01-01");
    expect(params.to_date).toBe("2026-07-31");
    expect(params.date_question_id).toBe(600204);
    expect(params.administration_id).toBe(42);
  });

  test("/escalation takes all four parameters", async () => {
    axios.mockResolvedValue({ data: { count: 0, results: [] } });
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
          ],
          columns: [{ key: "site", source: "parent_name" }],
        },
      }),
      ALL_FILTERS
    );
    await settle(probe);

    const { params } = axios.mock.calls[0][0];
    expect(params.administration_id).toBe(42);
    expect(params.date_question_id).toBe(600204);
  });

  test("geolocation takes `administration`, never `administration_id`", async () => {
    axios.mockResolvedValue({ data: [] });
    const probe = run(widget({ type: "map", config: {} }), ALL_FILTERS);
    await settle(probe);

    const { params } = callFor("maps/geolocation");
    // The wrong name here is accepted and silently dropped, not rejected.
    expect(params.administration).toBe(42);
    expect(params).not.toHaveProperty("administration_id");
    expect(params).not.toHaveProperty("date_question_id");
    expect(params.from_date).toBe("2026-01-01");
  });

  test("geolocation bounds dates on monitoring activity for a monitoring form", async () => {
    axios.mockResolvedValue({ data: [] });
    const probe = run(widget({ type: "map", config: {} }), ALL_FILTERS);
    await settle(probe);

    const { params } = callFor("maps/geolocation");
    expect(params.include_monitoring).toBe(true);
    expect(params.monitoring_form_id).toBe(MONITORING);
  });

  test("a map on the root form sends neither monitoring parameter", async () => {
    axios.mockResolvedValue({ data: [] });
    const probe = run(
      widget({ type: "map", form: ROOT, config: {} }),
      ALL_FILTERS
    );
    await settle(probe);

    const { params } = callFor("maps/geolocation");
    expect(params).not.toHaveProperty("include_monitoring");
    expect(params).not.toHaveProperty("monitoring_form_id");
  });

  test("changing the filters re-requests", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const w = widget();

    const probe = mount(() =>
      useWidgetData(w, NO_FILTERS, { rootFormId: ROOT })
    );
    await settle(probe);
    expect(axios).toHaveBeenCalledTimes(1);

    probe.rerender(
      <HookProbe
        run={() => useWidgetData(w, ALL_FILTERS, { rootFormId: ROOT })}
        onResult={() => {}}
      />
    );
    await waitFor(() => expect(axios).toHaveBeenCalledTimes(2));
    expect(axios.mock.calls[1][0].params.administration_id).toBe(42);
  });
});

// ── The map's second request ─────────────────────────────────────────

describe("map status lookup", () => {
  const mapWidget = widget({
    type: "map",
    config: {
      status_colors: { operational: "#64A73B", issue: "#e41a1c" },
    },
  });

  const mockBoth = (points, statuses) => {
    axios.mockImplementation((cfg) => {
      if (cfg.url.includes("maps/geolocation")) {
        return Promise.resolve({ data: points });
      }
      return Promise.resolve({ data: { data: statuses } });
    });
  };

  test("builds the formula from status_colors' own keys", async () => {
    mockBoth([], []);
    const probe = run(mapWidget);
    await settle(probe);

    const call = callFor("values/formula");
    expect(call.params.group_by).toBe("parent_id");
    expect(call.params.monitoring).toBe("latest");
    expect(call.params.form_id).toBe(MONITORING);

    const formula = JSON.parse(call.params.formula);
    expect(formula.buckets).toEqual([
      {
        value: "operational",
        label: "operational",
        all_of: [
          { question_id: QUESTION, op: "option_equals", value: "operational" },
        ],
      },
      {
        value: "issue",
        label: "issue",
        all_of: [
          { question_id: QUESTION, op: "option_equals", value: "issue" },
        ],
      },
    ]);
    expect(formula.default).toEqual({ value: "_no_info", label: "_no_info" });
  });

  test("empty status_colors makes one request, not two", async () => {
    axios.mockResolvedValue({ data: [] });
    const probe = run(widget({ type: "map", config: {} }));
    await settle(probe);

    // validate_shape() rejects an empty buckets array with a 400.
    expect(axios).toHaveBeenCalledTimes(1);
    expect(callFor("values/formula")).toBeUndefined();
  });

  test("joins status to points by datapoint id", async () => {
    mockBoth(
      [
        { id: 1, name: "Nadi", geo: [-17.78, 177.94] },
        { id: 2, name: "Ba", geo: [-17.53, 177.67] },
      ],
      [{ group: 1, label: "issue" }]
    );
    const probe = run(mapWidget);
    await settle(probe);

    expect(probe.latest().data).toEqual([
      { id: 1, name: "Nadi", geo: [-17.78, 177.94], status: "issue" },
      { id: 2, name: "Ba", geo: [-17.53, 177.67], status: null },
    ]);
  });
});

// ── Normalization to the renderers' input contract ───────────────────

describe("normalization", () => {
  test("kpi unwraps the envelope to {value}", async () => {
    axios.mockResolvedValue({
      data: { data: [{ value: 12480, label: "Total" }], labels: ["Total"] },
    });
    const probe = run(widget());
    await settle(probe);
    expect(probe.latest().data).toEqual({ value: 12480 });
  });

  test("kpi with no rows yields a null value rather than throwing", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(widget());
    await settle(probe);
    expect(probe.latest().data).toEqual({ value: null });
  });

  test("chart rows keep only label and value", async () => {
    axios.mockResolvedValue({
      data: {
        data: [
          {
            value: 55,
            label: "Operational",
            group: "operational",
            color: "#64A73B",
          },
          { value: 25, label: "Issue", group: "issue", color: "#e41a1c" },
        ],
        labels: ["Operational", "Issue"],
      },
    });
    const probe = run(
      widget({
        type: "pie",
        config: { measure: "current_state", group_by: "option" },
      })
    );
    await settle(probe);

    // akvo-charts infers its series from object keys, so a stray `group`
    // would be plotted as a second series.
    expect(probe.latest().data).toEqual([
      { label: "Operational", value: 55 },
      { label: "Issue", value: 25 },
    ]);
  });

  test("group_by=option lifts per-option colours onto renderWidget", async () => {
    axios.mockResolvedValue({
      data: {
        data: [
          {
            value: 55,
            label: "Operational",
            group: "operational",
            color: "#64A73B",
          },
          { value: 25, label: "Issue", group: "issue", color: "#e41a1c" },
        ],
        labels: ["Operational", "Issue"],
      },
    });
    const probe = run(
      widget({
        type: "pie",
        config: { measure: "current_state", group_by: "option" },
      })
    );
    await settle(probe);
    expect(probe.latest().renderWidget.color).toEqual(["#64A73B", "#e41a1c"]);
  });

  test("without group_by=option the widget colour is left alone", async () => {
    axios.mockResolvedValue({
      data: { data: [{ value: 5, label: "Jan" }], labels: ["Jan"] },
    });
    const probe = run(
      widget({
        type: "bar",
        config: { measure: "current_state", group_by: "month" },
      })
    );
    await settle(probe);
    expect(probe.latest().renderWidget.color).toBe("#64A73B");
  });

  test("stack_by derives stackMapping and passes rows through unprojected", async () => {
    axios.mockResolvedValue({
      data: {
        data: [
          { label: "Nadi", Operational: 12, Issue: 3 },
          { label: "Ba", Operational: 8, Issue: 1 },
        ],
        labels: ["Nadi", "Ba"],
        stack_labels: ["Operational", "Issue"],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "current_state",
          group_by: "parent_id",
          stack_by: "option",
        },
      })
    );
    await settle(probe);

    // The builder never writes stackMapping, so stacked charts render with
    // an empty mapping today. The per-stack columns ARE the data here, so
    // the rows must not be projected down to {label, value}.
    expect(probe.latest().renderWidget.config.stackMapping).toEqual({
      stack: ["Operational", "Issue"],
    });
    expect(probe.latest().data).toEqual([
      { label: "Nadi", Operational: 12, Issue: 3 },
      { label: "Ba", Operational: 8, Issue: 1 },
    ]);
  });

  test("table unwraps results and reports the page total", async () => {
    axios.mockResolvedValue({
      data: {
        count: 137,
        results: [{ id: 1, site: "Nadi Central EPS" }],
      },
    });
    const probe = run(
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [
            { type: "option_equals", question: QUESTION, value: "issue" },
          ],
          columns: [{ key: "site", source: "parent_name" }],
        },
      })
    );
    await settle(probe);

    expect(probe.latest().data).toEqual([{ id: 1, site: "Nadi Central EPS" }]);
    expect(probe.latest().pagination.total).toBe(137);
  });
});

// ── Failure is contained to the widget that failed ───────────────────

describe("failure containment", () => {
  test("a rejected request sets error and leaves data null", async () => {
    axios.mockRejectedValue(new Error("boom"));
    const probe = run(widget());
    await settle(probe);

    expect(probe.latest().error).toBeTruthy();
    expect(probe.latest().data).toBeNull();
  });

  test("one widget failing leaves its sibling's data intact", async () => {
    const failing = widget({ id: 1, question: 1 });
    const working = widget({ id: 2, question: 2 });

    axios.mockImplementation((cfg) =>
      cfg.params.question_id === 1
        ? Promise.reject(new Error("boom"))
        : Promise.resolve({
            data: { data: [{ value: 7, label: "Total" }], labels: ["Total"] },
          })
    );

    let a;
    let b;
    const Pair = () => {
      a = useWidgetData(failing, NO_FILTERS, { rootFormId: ROOT });
      b = useWidgetData(working, NO_FILTERS, { rootFormId: ROOT });
      return null;
    };
    render(<Pair />);

    await waitFor(() => expect(b.loading).toBe(false));
    await waitFor(() => expect(a.loading).toBe(false));

    expect(a.error).toBeTruthy();
    expect(b.error).toBeNull();
    expect(b.data).toEqual({ value: 7 });
  });
});

// ── Server-side pagination ───────────────────────────────────────────
//
// /escalation pages on the server and reports `count` for the whole set,
// returning one page of `results`. The hook hardcoded `page: 1`, so there
// was no way to reach page 2 — and because the renderer was handed a
// single page as its entire dataSource, antd concluded there was only one
// page and hid the pager. A table with page_size 3 over 5 datapoints
// showed 3 rows and no way to the other 2.

describe("table pagination", () => {
  const tableWidget = (config = {}) =>
    widget({
      type: "table",
      question: null,
      config: {
        criteria: [{ type: "option_equals", question: QUESTION, value: "x" }],
        columns: [{ key: "site", source: "parent_name" }],
        page_size: 3,
        ...config,
      },
    });

  test("the first request asks for page 1 at the configured size", async () => {
    axios.mockResolvedValue({ data: { count: 5, results: [] } });
    const probe = run(tableWidget());
    await settle(probe);

    const call = callFor("visualization/escalation");
    expect(call.params.page).toBe(1);
    expect(call.params.page_size).toBe(3);
  });

  test("it reports the whole set's size, not the page's", async () => {
    axios.mockResolvedValue({
      data: { count: 5, results: [{ id: 1 }, { id: 2 }, { id: 3 }] },
    });
    const probe = run(tableWidget());
    await settle(probe);

    expect(probe.latest().data).toHaveLength(3);
    expect(probe.latest().pagination.total).toBe(5);
    expect(probe.latest().pagination.current).toBe(1);
    expect(probe.latest().pagination.pageSize).toBe(3);
  });

  test("asking for another page re-requests it", async () => {
    axios.mockResolvedValue({ data: { count: 5, results: [] } });
    const probe = run(tableWidget());
    await settle(probe);

    await act(async () => {
      probe.latest().pagination.onChange(2);
    });
    await settle(probe);

    const pages = axios.mock.calls
      .map((c) => c[0])
      .filter((c) => c.url && c.url.includes("escalation"))
      .map((c) => c.params.page);
    expect(pages).toContain(2);
    expect(probe.latest().pagination.current).toBe(2);
  });

  test("a chart reports no pagination at all", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(widget({ type: "bar" }));
    await settle(probe);
    expect(probe.latest().pagination).toBeNull();
  });
});
