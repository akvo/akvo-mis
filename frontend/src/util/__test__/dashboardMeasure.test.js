import fs from "fs";
import path from "path";
import { expandMeasure, MONITORING_LATEST } from "../dashboardMeasure";

// Seeded fixture ids (form_seeder --test, example-vis-6).
const ROOT = 6001; // registration form
const MONITORING = 6002; // monitoring form, parent = 6001

const widget = (overrides = {}) => ({
  type: "kpi",
  form: MONITORING,
  question: 600203,
  ...overrides,
});

describe("expandMeasure", () => {
  test("current_state counts sites by their latest monitoring submission", () => {
    expect(
      expandMeasure(widget({ config: { measure: "current_state" } }), ROOT)
    ).toEqual({ monitoring: "latest", sum_by: "parent_id" });
  });

  test("all_submissions counts submissions, and never sums by parent", () => {
    const out = expandMeasure(
      widget({ config: { measure: "all_submissions" } }),
      ROOT
    );
    expect(out.monitoring).toBe("all");
    // Asserted as an absence rather than a value: sum_by=parent_id on
    // monitoring=all silently turns "42 visits" back into "42 sites".
    expect(out).not.toHaveProperty("sum_by");
  });

  test("a widget on the registration form emits neither parameter", () => {
    const out = expandMeasure(
      widget({ form: ROOT, config: { measure: "current_state" } }),
      ROOT
    );
    expect(out).not.toHaveProperty("monitoring");
    expect(out).not.toHaveProperty("sum_by");
  });

  test("include_unmonitored maps to include_unanswered under both measures", () => {
    expect(
      expandMeasure(
        widget({
          config: { measure: "current_state", include_unmonitored: true },
        }),
        ROOT
      )
    ).toEqual({
      monitoring: "latest",
      sum_by: "parent_id",
      include_unanswered: true,
    });
    expect(
      expandMeasure(
        widget({
          config: { measure: "all_submissions", include_unmonitored: true },
        }),
        ROOT
      ).include_unanswered
    ).toBe(true);
  });

  test("include_unmonitored false or absent emits no key at all", () => {
    const off = expandMeasure(
      widget({
        config: { measure: "current_state", include_unmonitored: false },
      }),
      ROOT
    );
    const absent = expandMeasure(
      widget({ config: { measure: "current_state" } }),
      ROOT
    );
    expect(off).not.toHaveProperty("include_unanswered");
    expect(absent).not.toHaveProperty("include_unanswered");
  });

  test("a widget with no config does not throw", () => {
    // No `config` key at all, which is what a section_title carries and
    // what a widget mid-edit can briefly look like.
    const bare = { type: "kpi", form: MONITORING, question: 600203 };
    expect(() => expandMeasure(bare, ROOT)).not.toThrow();
    expect(expandMeasure(bare, ROOT)).toEqual({});
    expect(expandMeasure(null, ROOT)).toEqual({});
  });

  test("MONITORING_LATEST is exported for the map's formula request", () => {
    expect(MONITORING_LATEST).toBe("latest");
  });
});

// ── The single-writer guard (spec D-3) ────────────────────────────────
//
// The measure expansion is the only place `monitoring=` is written. A
// second writer is how "42 sites are operational" quietly becomes "42
// visits reported operational" — both numbers look reasonable, and only
// one answers the question the widget's title asks.

const SRC = path.join(__dirname, "..", "..");

// VIZ-009 (#313) deleted the legacy renderer, so the expansion now has the
// single writer VIZ-008 specified — nothing else may join this list.
const ALLOWED = ["util/dashboardMeasure.js"];

// `monitoring:` in an object literal, or `monitoring=` in a query string.
// `include_monitoring` is a different parameter on a different endpoint
// and is deliberately not matched.
const WRITES_PARAM = /(?<![_\w])monitoring\s*[:=]\s*["'`]/;

const walk = (dir, out = []) => {
  fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "__test__" && entry.name !== "node_modules") {
        walk(full, out);
      }
      return;
    }
    if (/\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)) {
      out.push(full);
    }
  });
  return out;
};

describe("monitoring= has exactly one writer", () => {
  test("no module outside the allow-list writes it", () => {
    const offenders = walk(SRC)
      .filter((file) => WRITES_PARAM.test(fs.readFileSync(file, "utf8")))
      .map((file) => path.relative(SRC, file))
      .filter((rel) => !ALLOWED.includes(rel));
    expect(offenders).toEqual([]);
  });

  test("the allow-list has no stale entries", () => {
    // A allow-listed file that stopped writing the parameter should be
    // removed from the list, not left as cover for a future violation.
    ALLOWED.forEach((rel) => {
      const full = path.join(SRC, rel);
      expect(fs.existsSync(full)).toBe(true);
      expect(WRITES_PARAM.test(fs.readFileSync(full, "utf8"))).toBe(true);
    });
  });
});
