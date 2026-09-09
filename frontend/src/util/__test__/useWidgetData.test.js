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

// The server needs `dashboard_slug` on every widget request to decide what
// an anonymous caller may see (VIZ-011 Tasks 7, 8, 10). It goes out
// unconditionally — not only when signed out — because the server ignores
// it for an authenticated caller, and one always-present parameter is
// cheaper to get right than a public-mode flag threaded through three
// components.
describe("dashboard_slug", () => {
  test("is sent on every request the hook builds", async () => {
    axios.mockResolvedValue({ data: { data: [], count: 0, results: [] } });

    const cases = [
      widget({ type: "bar", config: { measure: "current_state" } }),
      widget({
        type: "table",
        question: null,
        config: {
          criteria: [],
          columns: [{ key: "site", source: "parent_name" }],
        },
      }),
      // status_colors is what makes buildStatusRequest fire its own
      // request (see below) on top of the map's geolocation request --
      // an empty config, as used above, asks for neither bucket.
      widget({
        type: "map",
        config: { status_colors: { Operational: "#64A73B" } },
      }),
    ];

    const probes = cases.map((w) =>
      mount(() =>
        useWidgetData(w, NO_FILTERS, {
          rootFormId: ROOT,
          dashboardSlug: "water-points",
        })
      )
    );
    await Promise.all(probes.map((probe) => settle(probe)));

    const calls = axios.mock.calls.map((c) => c[0]);
    // All four request builders, proven by endpoint rather than by count:
    // values (bar), escalation (table), geolocation and formula (the map's
    // two requests, geo points plus buildStatusRequest's status join).
    expect(calls.some((c) => c.url.includes("visualization/values"))).toBe(
      true
    );
    expect(calls.some((c) => c.url.includes("visualization/escalation"))).toBe(
      true
    );
    expect(calls.some((c) => c.url.includes("maps/geolocation"))).toBe(true);
    expect(
      calls.some((c) => c.url.includes("visualization/values/formula"))
    ).toBe(true);
    calls.forEach((call) => {
      expect(call.params.dashboard_slug).toBe("water-points");
    });
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

  // The regression the projection introduced: `_stack_parent_by_month`
  // and `_stack_parent_by_date` key their category `month`/`date`, not
  // `label`, so a number question stacked by site drew a chart whose
  // every bar was `undefined`.
  test("a parent-stacked row keyed by date still finds its category", async () => {
    axios.mockResolvedValue({
      data: {
        data: [
          { date: "2026-07-10", "Site A": 12, "Site B": 5 },
          { date: "2026-07-13", "Site A": 8, "Site B": 3 },
        ],
        labels: ["2026-07-10", "2026-07-13"],
        stack_labels: ["Site A", "Site B"],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "current_state",
          group_by: "date",
          stack_by: "parent_id",
        },
      })
    );
    await settle(probe);
    expect(probe.latest().data).toEqual([
      { label: "2026-07-10", "Site A": 12, "Site B": 5 },
      { label: "2026-07-13", "Site A": 8, "Site B": 3 },
    ]);
  });

  test("a parent-stacked row keyed by month does too", async () => {
    axios.mockResolvedValue({
      data: {
        data: [{ month: "Jul 2026", "Site A": 12 }],
        labels: ["Jul 2026"],
        stack_labels: ["Site A"],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "current_state",
          group_by: "month",
          stack_by: "parent_id",
        },
      })
    );
    await settle(probe);
    expect(probe.latest().data).toEqual([{ label: "Jul 2026", "Site A": 12 }]);
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

  test("stack_by keeps the stack columns and drops everything else", async () => {
    axios.mockResolvedValue({
      data: {
        data: [
          { label: "Nadi", group: 7200, Operational: 12, Issue: 3 },
          { label: "Ba", group: 7201, Operational: 8, Issue: 1 },
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

    expect(probe.latest().renderWidget.config.stackMapping).toEqual({
      stack: ["Operational", "Issue"],
    });
    // `group` must not survive: akvo-charts makes a series of every key
    // but the first, so leaving it in plotted the datapoint id as a bar
    // — 7200 tall, next to stacks of 12 and 3.
    expect(probe.latest().data).toEqual([
      { label: "Nadi", Operational: 12, Issue: 3 },
      { label: "Ba", Operational: 8, Issue: 1 },
    ]);
  });

  test("a stack column missing from a row becomes zero, not a hole", async () => {
    axios.mockResolvedValue({
      data: {
        data: [{ label: "Nadi", group: 7200, Operational: 12 }],
        labels: ["Nadi"],
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
    expect(probe.latest().data).toEqual([
      { label: "Nadi", Operational: 12, Issue: 0 },
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

// =========================================================
// Stacking by another question (VIZ-015)
// =========================================================

describe("stack_question", () => {
  test("reaches the request only when the author picked one", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          stack_by: "option",
          stack_question: 600204,
        },
      })
    );
    await settle(probe);
    expect(axios.mock.calls[0][0].params.stack_question_id).toBe(600204);
  });

  test("an unstacked widget sends nothing new", async () => {
    // compact() drops the null, so the request — and therefore the
    // response — is byte-identical to what it was before this feature.
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: { measure: "all_submissions", group_by: "option" },
      })
    );
    await settle(probe);
    expect(axios.mock.calls[0][0].params).not.toHaveProperty(
      "stack_question_id"
    );
  });

  test("stack colours reach renderWidget when every option has one", async () => {
    axios.mockResolvedValue({
      data: {
        data: [{ label: "Active", "Feature X": 1, "Feature Y": 2 }],
        labels: ["Active"],
        stack_labels: ["Feature X", "Feature Y"],
        colors: ["#1f77b4", "#ff7f0e"],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          stack_by: "option",
          stack_question: 600204,
        },
      })
    );
    await settle(probe);
    expect(probe.latest().renderWidget.color).toEqual(["#1f77b4", "#ff7f0e"]);
    expect(probe.latest().renderWidget.config.stackMapping).toEqual({
      stack: ["Feature X", "Feature Y"],
    });
  });

  test("a partly-coloured question falls back to the widget colour", async () => {
    // QuestionOptions.color is nullable and nothing defaults it, so this
    // is the normal shape on an author-built form. Passing the array on
    // would colour one series and leave the rest to whatever the chart
    // library does with a null — possibly a colour already in use.
    axios.mockResolvedValue({
      data: {
        data: [{ label: "Active", "Feature X": 1, "Feature Y": 2 }],
        labels: ["Active"],
        stack_labels: ["Feature X", "Feature Y"],
        colors: ["#1f77b4", null],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          stack_by: "option",
          stack_question: 600204,
        },
      })
    );
    await settle(probe);
    expect(probe.latest().renderWidget.color).toBe("#64A73B");
  });

  test("no colours at all falls back too", async () => {
    axios.mockResolvedValue({
      data: {
        data: [{ label: "Active", "Feature X": 1 }],
        labels: ["Active"],
        stack_labels: ["Feature X"],
        colors: [],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          stack_by: "option",
          stack_question: 600204,
        },
      })
    );
    await settle(probe);
    expect(probe.latest().renderWidget.color).toBe("#64A73B");
  });
});

// =========================================================
// Cross-form stacking (VIZ-015.a)
// =========================================================
//
// Bars from the widget's form, stacks from another, joined on `group`.
// Two requests where every other chart makes one.

describe("cross-form stacking", () => {
  const crossWidget = (overrides = {}) =>
    widget({
      type: "bar",
      config: {
        measure: "current_state",
        group_by: "parent_id",
        stack_by: "option",
        stack_question: 600204,
        stack_form: 6001,
        ...overrides,
      },
    });

  const CATEGORY = {
    data: [{ label: "Nadi", group: 7, Surface: 1, Borehole: 0 }],
    stack_labels: ["Surface", "Borehole"],
    colors: ["#111111", "#222222"],
  };
  const SERIES = {
    data: [{ label: "Nadi", group: 7, WAF: 0, MRD: 1 }],
    stack_labels: ["WAF", "MRD"],
    colors: ["#1f77b4", "#ff7f0e"],
  };

  const bySeriesForm = (config) =>
    String(config.params?.form_id) === "6001" ? SERIES : CATEGORY;

  test("no stack_form means one request, as before", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: { measure: "current_state", group_by: "option" },
      })
    );
    await settle(probe);
    expect(axios.mock.calls).toHaveLength(1);
  });

  test("a stack_form equal to the widget's form is not cross-form", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(crossWidget({ stack_form: MONITORING }));
    await settle(probe);
    expect(axios.mock.calls).toHaveLength(1);
  });

  test("a stack_form without a stack_question asks for nothing extra", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(crossWidget({ stack_question: null }));
    await settle(probe);
    expect(axios.mock.calls).toHaveLength(1);
  });

  test("a cross-form widget issues exactly two values calls", async () => {
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget());
    await settle(probe);
    expect(axios.mock.calls).toHaveLength(2);
  });

  test("the primary call does not carry stack_question_id", async () => {
    // It names a question on ANOTHER form, so sending it here is a 400
    // twice over: not on form_id, and stack_question_id requires
    // group_by=option while a cross-form chart is pinned to parent_id.
    // Asserting only the call COUNT missed this entirely.
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget());
    await settle(probe);
    const primary = axios.mock.calls
      .map((c) => c[0])
      .find((c) => String(c.params.form_id) === String(MONITORING));
    expect(primary.params).not.toHaveProperty("stack_question_id");
  });

  test("a same-form stack still carries stack_question_id", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "current_state",
          group_by: "option",
          stack_by: "option",
          stack_question: 600204,
        },
      })
    );
    await settle(probe);
    expect(axios.mock.calls[0][0].params.stack_question_id).toBe(600204);
  });

  test("the series call pins group_by and stack_by", async () => {
    // Not the author's to choose: the join keys on the registration
    // datapoint, which is only a key under parent_id.
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget());
    await settle(probe);
    const series = axios.mock.calls
      .map((c) => c[0])
      .find((c) => String(c.params.form_id) === "6001");
    expect(series.params.group_by).toBe("parent_id");
    expect(series.params.stack_by).toBe("option");
    expect(series.params.question_id).toBe(600204);
  });

  test("the series call carries the dashboard filters", async () => {
    // Otherwise the bars and the segments describe different populations,
    // which reads as a data bug rather than a configuration one.
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget(), {
      from_date: "2025-01-01",
      to_date: "2025-06-30",
      administration_id: 42,
    });
    await settle(probe);
    const series = axios.mock.calls
      .map((c) => c[0])
      .find((c) => String(c.params.form_id) === "6001");
    expect(series.params.from_date).toBe("2025-01-01");
    expect(series.params.to_date).toBe("2025-06-30");
    expect(series.params.administration_id).toBe(42);
  });

  test("the join runs before the projection", async () => {
    // The projection drops `group`, the join key. Reversed, the join
    // matches nothing and the chart renders empty with no error anywhere.
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget());
    await settle(probe);
    expect(probe.latest().data).toEqual([{ label: "Surface", WAF: 0, MRD: 1 }]);
  });

  test("the legend describes the series question, not the bars", async () => {
    axios.mockImplementation((config) =>
      Promise.resolve({ data: bySeriesForm(config) })
    );
    const probe = run(crossWidget());
    await settle(probe);
    expect(probe.latest().renderWidget.config.stackMapping).toEqual({
      stack: ["WAF", "MRD"],
    });
    expect(probe.latest().renderWidget.color).toEqual(["#1f77b4", "#ff7f0e"]);
  });

  test("a partly-null series palette falls back to the widget colour", async () => {
    axios.mockImplementation((config) =>
      Promise.resolve({
        data:
          String(config.params?.form_id) === "6001"
            ? { ...SERIES, colors: ["#1f77b4", null] }
            : CATEGORY,
      })
    );
    const probe = run(crossWidget());
    await settle(probe);
    expect(probe.latest().renderWidget.color).toBe("#64A73B");
  });
});

describe("a stack the server declined to draw", () => {
  test("falls back to the unstacked projection", async () => {
    // Asked to cross-tab a question against itself, the backend returns
    // the plain option breakdown — real rows, but no stack_labels.
    // Trusting config.stack_by there threw all of them away and drew an
    // empty chart with a bare axis.
    axios.mockResolvedValue({
      data: {
        data: [
          {
            value: 6,
            label: "Water Authority",
            group: "waf",
            color: "#1b9e77",
          },
          {
            value: 4,
            label: "Mineral Resources",
            group: "mrd",
            color: "#d95f02",
          },
        ],
        labels: ["Water Authority", "Mineral Resources"],
      },
    });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          stack_by: "option",
        },
      })
    );
    await settle(probe);
    expect(probe.latest().data).toEqual([
      { label: "Water Authority", value: 6 },
      { label: "Mineral Resources", value: 4 },
    ]);
  });
});

describe("value question", () => {
  test("reaches the request only when the author picked one", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: {
          measure: "all_submissions",
          group_by: "option",
          value_question: 600202,
          repeat_agg: "sum",
        },
      })
    );
    await settle(probe);
    expect(axios.mock.calls[0][0].params.value_question_id).toBe(600202);
    expect(axios.mock.calls[0][0].params.repeat_agg).toBe("sum");
  });

  test("a counting widget sends nothing new", async () => {
    axios.mockResolvedValue({ data: { data: [], labels: [] } });
    const probe = run(
      widget({
        type: "bar",
        config: { measure: "all_submissions", group_by: "option" },
      })
    );
    await settle(probe);
    expect(axios.mock.calls[0][0].params).not.toHaveProperty(
      "value_question_id"
    );
  });
});
