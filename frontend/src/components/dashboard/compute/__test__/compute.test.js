import { rotateToFiscalOrder } from "../fiscalMonthRotation";
import {
  computeComplianceStackData,
  fails,
  getCompliantCount,
} from "../compliance";
import { computeCrossTab } from "../crossTab";
import {
  computeAccessibilityBucket,
  deriveAccessibilityBucket,
} from "../accessibility";
import { computeKpiStack } from "../kpiStack";

describe("rotateToFiscalOrder", () => {
  const rows = [
    { group: "2025-01", value: 1, label: "Jan" },
    { group: "2025-04", value: 4, label: "Apr" },
    { group: "2025-07", value: 7, label: "Jul" },
    { group: "2025-10", value: 10, label: "Oct" },
    { group: "2025-12", value: 12, label: "Dec" },
  ];

  test("startMonth=7 rotates Jan-Jun to the tail", () => {
    const out = rotateToFiscalOrder(rows, 7).map((r) => r.group);
    expect(out).toEqual([
      "2025-07",
      "2025-10",
      "2025-12",
      "2025-01",
      "2025-04",
    ]);
  });

  test("startMonth=1 is a no-op after sorting", () => {
    const shuffled = [rows[3], rows[0], rows[2], rows[1], rows[4]];
    const out = rotateToFiscalOrder(shuffled, 1).map((r) => r.group);
    expect(out).toEqual([
      "2025-01",
      "2025-04",
      "2025-07",
      "2025-10",
      "2025-12",
    ]);
  });

  test("handles empty input", () => {
    expect(rotateToFiscalOrder([], 7)).toEqual([]);
    expect(rotateToFiscalOrder(null, 7)).toEqual([]);
  });
});

describe("compliance.fails", () => {
  test("returns false for null/undefined (no data)", () => {
    expect(fails({ max: 0 }, null)).toBe(false);
    let u;
    expect(fails({ max: 0 }, u)).toBe(false);
  });
  test("respects max bound", () => {
    expect(fails({ max: 0 }, 0)).toBe(false);
    expect(fails({ max: 0 }, 1)).toBe(true);
  });
  test("respects min bound", () => {
    expect(fails({ min: 6.5, max: 8.5 }, 6.0)).toBe(true);
    expect(fails({ min: 6.5, max: 8.5 }, 7.0)).toBe(false);
    expect(fails({ min: 6.5, max: 8.5 }, 9.0)).toBe(true);
  });
});

describe("computeComplianceStackData", () => {
  const parameters = [
    { key: "e_coli", label: "E. coli", threshold: { max: 0 } },
    { key: "ph", label: "pH", threshold: { min: 6.5, max: 8.5 } },
    { key: "hidden_one", label: "Hidden", threshold: { max: 0 }, hide: true },
  ];

  test("classifies two EPS as Yes and one as No with failure tally", () => {
    const responses = {
      e_coli: {
        data: [
          { group: "1", label: "A", value: 0 },
          { group: "2", label: "B", value: 5 },
          { group: "3", label: "C", value: 0 },
        ],
      },
      ph: {
        data: [
          { group: "1", label: "A", value: 7.0 },
          { group: "2", label: "B", value: 7.0 },
          { group: "3", label: "C", value: 9.5 },
        ],
      },
    };

    const out = computeComplianceStackData(parameters, responses);
    expect(out.yesCount).toBe(1); // EPS 1 only
    expect(out.noCount).toBe(2); // EPS 2 (e_coli), EPS 3 (ph)
    expect(out.stackLabels).toEqual(["Compliant", "E. coli", "pH"]);

    const yesRow = out.data.find((d) => d.compliance === "Yes");
    const noRow = out.data.find((d) => d.compliance === "No");
    expect(yesRow.Compliant).toBe(1);
    expect(noRow["E. coli"]).toBe(1);
    expect(noRow.pH).toBe(1);
  });

  test("skips hidden parameters", () => {
    const out = computeComplianceStackData(parameters, {});
    expect(out.stackLabels).not.toContain("Hidden");
  });

  test("missing value for a parameter counts as no-data, not violation", () => {
    const responses = {
      e_coli: { data: [{ group: "1", label: "A", value: 0 }] },
      // ph intentionally has no entry for group "1"
    };
    const out = computeComplianceStackData(parameters, responses);
    expect(out.yesCount).toBe(1);
    expect(out.noCount).toBe(0);
  });

  describe("include_unanswered support", () => {
    const responses = {
      e_coli: {
        data: [
          { group: "1", label: "A", value: 0 },
          { group: "2", label: "B", value: 5 },
          { group: "3", label: "C", value: 0 },
        ],
      },
      ph: {
        data: [
          { group: "1", label: "A", value: 7.0 },
          { group: "2", label: "B", value: 7.0 },
          { group: "3", label: "C", value: 9.5 },
        ],
      },
    };

    test("2-arg signature unchanged when options omitted", () => {
      const out = computeComplianceStackData(parameters, responses);
      expect(out.data).toHaveLength(2);
      expect(out.stackLabels).toEqual(["Compliant", "E. coli", "pH"]);
      expect(out.noInfoCount).toBe(0);
    });

    test("appends third row when totalRegistered exceeds yes+no", () => {
      const out = computeComplianceStackData(parameters, responses, {
        totalRegistered: 10,
      });
      expect(out.yesCount).toBe(1);
      expect(out.noCount).toBe(2);
      expect(out.noInfoCount).toBe(7);
      expect(out.data).toHaveLength(3);
      expect(out.data[2]).toEqual({
        compliance: "No information available",
        "No information available": 7,
      });
      expect(out.stackLabels).toEqual([
        "Compliant",
        "E. coli",
        "pH",
        "No information available",
      ]);
    });

    test("omits third row when totalRegistered equals yes+no", () => {
      const out = computeComplianceStackData(parameters, responses, {
        totalRegistered: 3,
      });
      expect(out.noInfoCount).toBe(0);
      expect(out.data).toHaveLength(2);
      expect(out.stackLabels).toEqual(["Compliant", "E. coli", "pH"]);
    });

    test("clamps to zero when totalRegistered is less than yes+no", () => {
      const out = computeComplianceStackData(parameters, responses, {
        totalRegistered: 1,
      });
      expect(out.noInfoCount).toBe(0);
      expect(out.data).toHaveLength(2);
    });

    test("respects custom noInfoLabel from i18n", () => {
      const out = computeComplianceStackData(parameters, responses, {
        totalRegistered: 10,
        noInfoLabel: "Sin información",
      });
      expect(out.data[2].compliance).toBe("Sin información");
    });

    test("does nothing when totalRegistered is undefined", () => {
      const out = computeComplianceStackData(parameters, responses, {});
      expect(out.data).toHaveLength(2);
      expect(out.noInfoCount).toBe(0);
      expect(out.stackLabels).not.toContain("No information available");
    });

    test("does nothing when totalRegistered is non-number", () => {
      const cases = [null, "10", NaN, true, []];
      cases.forEach((bad) => {
        const out = computeComplianceStackData(parameters, responses, {
          totalRegistered: bad,
        });
        expect(out.data).toHaveLength(2);
        expect(out.noInfoCount).toBe(0);
      });
    });
  });
});

describe("getCompliantCount", () => {
  const parameters = [
    { key: "e_coli", label: "E. coli", threshold: { max: 0 } },
    { key: "ph", label: "pH", threshold: { min: 6.5, max: 8.5 } },
    { key: "hidden_one", label: "Hidden", threshold: { max: 0 }, hide: true },
  ];

  test("returns 0 when responses are empty", () => {
    expect(getCompliantCount(parameters, {})).toBe(0);
    expect(getCompliantCount(parameters, null)).toBe(0);
  });

  test("returns 0 when parameters list is empty", () => {
    expect(getCompliantCount([], { e_coli: { data: [] } })).toBe(0);
    expect(getCompliantCount(null, { e_coli: { data: [] } })).toBe(0);
  });

  test("counts only parents whose active params are all within threshold", () => {
    const responses = {
      e_coli: {
        data: [
          { group: "1", label: "A", value: 0 },
          { group: "2", label: "B", value: 5 },
          { group: "3", label: "C", value: 0 },
        ],
      },
      ph: {
        data: [
          { group: "1", label: "A", value: 7.0 },
          { group: "2", label: "B", value: 7.0 },
          { group: "3", label: "C", value: 9.5 },
        ],
      },
    };
    expect(getCompliantCount(parameters, responses)).toBe(1);
  });

  test("skips hidden parameters (agrees with computeComplianceStackData)", () => {
    const responses = {
      e_coli: { data: [{ group: "1", label: "A", value: 0 }] },
      ph: { data: [{ group: "1", label: "A", value: 7.0 }] },
      hidden_one: { data: [{ group: "1", label: "A", value: 999 }] },
    };
    expect(getCompliantCount(parameters, responses)).toBe(1);
  });

  test("missing value for a parameter is treated as no-data, not violation", () => {
    const responses = {
      e_coli: { data: [{ group: "1", label: "A", value: 0 }] },
      // ph intentionally has no entry for group "1"
    };
    expect(getCompliantCount(parameters, responses)).toBe(1);
  });

  test("matches computeComplianceStackData.yesCount across fixtures", () => {
    const responses = {
      e_coli: {
        data: [
          { group: "10", label: "A", value: 0 },
          { group: "11", label: "B", value: 1 },
        ],
      },
      ph: {
        data: [
          { group: "10", label: "A", value: 7.0 },
          { group: "11", label: "B", value: 7.0 },
        ],
      },
    };
    const stack = computeComplianceStackData(parameters, responses);
    expect(getCompliantCount(parameters, responses)).toBe(stack.yesCount);
  });
});

describe("computeCrossTab (column-per-option shape)", () => {
  // Backend response shape after akvo-mis-bvt:
  //   {data: [{label: parent_name, group: parent_id, [opt_label]: count}]}
  // One row per parent; option columns carry 0|1 for single-select,
  // 0|N for multi-select. stack_labels lists option columns.

  test("empty responses → []", () => {
    expect(computeCrossTab({ category: null, series: null })).toEqual([]);
    expect(
      computeCrossTab({ category: { data: [] }, series: { data: [] } })
    ).toEqual([]);
    expect(computeCrossTab(null)).toEqual([]);
  });

  test("single parent single-select category, single-select series → 1-row 1-cell", () => {
    const out = computeCrossTab({
      category: {
        data: [
          {
            label: "Site Alpha",
            group: 42,
            Borehole: 1,
            "Surface Water Project": 0,
          },
        ],
      },
      series: {
        data: [{ label: "Site Alpha", group: 42, WAF: 1, Rotary: 0 }],
      },
    });
    expect(out).toEqual([{ category: "Borehole", WAF: 1 }]);
  });

  test("multiple parents under same category tally up", () => {
    const out = computeCrossTab({
      category: {
        data: [
          { label: "A", group: 1, Borehole: 1, Desalination: 0 },
          { label: "B", group: 2, Borehole: 1, Desalination: 0 },
          { label: "C", group: 3, Borehole: 0, Desalination: 1 },
        ],
      },
      series: {
        data: [
          { label: "A", group: 1, WAF: 1, Rotary: 0 },
          { label: "B", group: 2, WAF: 1, Rotary: 0 },
          { label: "C", group: 3, WAF: 0, Rotary: 1 },
        ],
      },
    });
    const row = (c) => out.find((r) => r.category === c);
    expect(row("Borehole").WAF).toBe(2);
    expect(row("Desalination").Rotary).toBe(1);
  });

  test("multi-option series: one parent with two agencies increments both cells", () => {
    const out = computeCrossTab({
      category: {
        data: [
          {
            label: "A",
            group: 7,
            "Surface Water Project": 1,
            Borehole: 0,
          },
        ],
      },
      series: {
        data: [{ label: "A", group: 7, WAF: 1, Rotary: 1, Habitat: 0 }],
      },
    });
    expect(out).toEqual([
      { category: "Surface Water Project", WAF: 1, Rotary: 1 },
    ]);
  });

  test("parent in series but not in category is dropped (no inferred category)", () => {
    const out = computeCrossTab({
      category: {
        data: [{ label: "A", group: 1, Borehole: 1 }],
      },
      series: {
        data: [
          { label: "A", group: 1, WAF: 1 },
          { label: "Ghost", group: 99, WAF: 1 },
        ],
      },
    });
    expect(out).toEqual([{ category: "Borehole", WAF: 1 }]);
  });

  test("parent in category but not in series creates row with just category", () => {
    const out = computeCrossTab({
      category: { data: [{ label: "A", group: 1, Borehole: 1 }] },
      series: { data: [] },
    });
    expect(out).toEqual([{ category: "Borehole" }]);
  });

  test("parent with no option selected (all zeros) is skipped — no category inferred", () => {
    const out = computeCrossTab({
      category: {
        data: [
          { label: "A", group: 1, Borehole: 0, Desalination: 0 },
          { label: "B", group: 2, Borehole: 1, Desalination: 0 },
        ],
      },
      series: {
        data: [
          { label: "A", group: 1, WAF: 1 },
          { label: "B", group: 2, WAF: 1 },
        ],
      },
    });
    // Only B contributes — A has no category answer.
    expect(out).toEqual([{ category: "Borehole", WAF: 1 }]);
  });

  test("category with 0 count in series row leaves cell absent (not 0)", () => {
    const out = computeCrossTab({
      category: { data: [{ label: "A", group: 1, Borehole: 1 }] },
      series: { data: [{ label: "A", group: 1, WAF: 0, Rotary: 0 }] },
    });
    expect(out).toEqual([{ category: "Borehole" }]);
  });

  test("handles missing .data arrays", () => {
    expect(computeCrossTab({ category: {}, series: {} })).toEqual([]);
  });
});

describe("deriveAccessibilityBucket (A.2 rule)", () => {
  test("sample=yes ∧ issues=no → easily_accessible", () => {
    expect(deriveAccessibilityBucket("yes", "no")).toBe("easily_accessible");
  });
  test("sample=yes ∧ issues missing → easily_accessible", () => {
    let u;
    expect(deriveAccessibilityBucket("yes", u)).toBe("easily_accessible");
    expect(deriveAccessibilityBucket("yes", null)).toBe("easily_accessible");
  });
  test("sample=yes ∧ issues=yes → accessible_with_issues", () => {
    expect(deriveAccessibilityBucket("yes", "yes")).toBe(
      "accessible_with_issues"
    );
  });
  test("sample=no → not_accessible (regardless of issues)", () => {
    let u;
    expect(deriveAccessibilityBucket("no", "yes")).toBe("not_accessible");
    expect(deriveAccessibilityBucket("no", "no")).toBe("not_accessible");
    expect(deriveAccessibilityBucket("no", u)).toBe("not_accessible");
  });
  test("no sample record → null (EXCLUDED per US-4 AC)", () => {
    let u;
    expect(deriveAccessibilityBucket(u, "yes")).toBeNull();
    expect(deriveAccessibilityBucket(null, "no")).toBeNull();
  });
});

describe("computeAccessibilityBucket (column-per-option shape)", () => {
  // Backend response shape per akvo-mis-bvt:
  //   {data: [{label: parent_name, group: parent_id, Yes: 1|0, No: 1|0}]}
  // Option labels come from the option question's QuestionOptions.

  const labels = {
    easily_accessible: "Easily accessible",
    accessible_with_issues: "Accessible with issues",
    not_accessible: "Not accessible",
  };

  test("empty inputs → single row with 0 counts", () => {
    expect(computeAccessibilityBucket(null, labels)).toEqual([
      {
        category: "Accessibility",
        "Easily accessible": 0,
        "Accessible with issues": 0,
        "Not accessible": 0,
      },
    ]);
    expect(
      computeAccessibilityBucket(
        { sample: { data: [] }, issues: { data: [] } },
        labels
      )
    ).toEqual([
      {
        category: "Accessibility",
        "Easily accessible": 0,
        "Accessible with issues": 0,
        "Not accessible": 0,
      },
    ]);
  });

  test("tallies all 3 A.2 buckets across multiple parents", () => {
    const out = computeAccessibilityBucket(
      {
        sample: {
          data: [
            { label: "A", group: 1, Yes: 1, No: 0 }, // easily accessible
            { label: "B", group: 2, Yes: 1, No: 0 }, // accessible with issues
            { label: "C", group: 3, Yes: 0, No: 1 }, // not accessible
            // parent 4 has no sample record → excluded
          ],
        },
        issues: {
          data: [
            { label: "A", group: 1, Yes: 0, No: 1 },
            { label: "B", group: 2, Yes: 1, No: 0 },
            { label: "C", group: 3, Yes: 1, No: 0 },
            { label: "D", group: 4, Yes: 1, No: 0 }, // parent w/o sample → excluded
          ],
        },
      },
      labels
    );
    expect(out).toEqual([
      {
        category: "Accessibility",
        "Easily accessible": 1,
        "Accessible with issues": 1,
        "Not accessible": 1,
      },
    ]);
  });

  test("parent with sample=yes but no issues record → easily_accessible", () => {
    const out = computeAccessibilityBucket(
      {
        sample: { data: [{ label: "A", group: 1, Yes: 1, No: 0 }] },
        issues: { data: [] },
      },
      labels
    );
    expect(out[0]["Easily accessible"]).toBe(1);
    expect(out[0]["Accessible with issues"]).toBe(0);
  });

  test("sample=no wins over issues=yes → not_accessible", () => {
    const out = computeAccessibilityBucket(
      {
        sample: { data: [{ label: "A", group: 1, Yes: 0, No: 1 }] },
        issues: { data: [{ label: "A", group: 1, Yes: 1, No: 0 }] },
      },
      labels
    );
    expect(out[0]["Not accessible"]).toBe(1);
    expect(out[0]["Accessible with issues"]).toBe(0);
  });

  test("respects custom labels", () => {
    const customLabels = {
      easily_accessible: "Bagus",
      accessible_with_issues: "Oke lah",
      not_accessible: "Gagal",
    };
    const out = computeAccessibilityBucket(
      {
        sample: { data: [{ label: "A", group: 1, Yes: 0, No: 1 }] },
        issues: { data: [] },
      },
      customLabels
    );
    expect(out[0].Gagal).toBe(1);
    expect(out[0].Bagus).toBe(0);
  });

  test("parent with all-zero sample row is excluded (no clear answer)", () => {
    const out = computeAccessibilityBucket(
      {
        sample: { data: [{ label: "A", group: 1, Yes: 0, No: 0 }] },
        issues: { data: [] },
      },
      labels
    );
    expect(out[0]["Easily accessible"]).toBe(0);
    expect(out[0]["Accessible with issues"]).toBe(0);
    expect(out[0]["Not accessible"]).toBe(0);
  });

  test("handles missing .data arrays", () => {
    expect(
      computeAccessibilityBucket({ sample: {}, issues: {} }, labels)
    ).toEqual([
      {
        category: "Accessibility",
        "Easily accessible": 0,
        "Accessible with issues": 0,
        "Not accessible": 0,
      },
    ]);
  });
});

describe("computeKpiStack", () => {
  const segments2 = [
    { key: "operational", label: "Operational" },
    { key: "issues", label: "Issues with the system" },
  ];

  test("empty segments → row with just the category", () => {
    expect(computeKpiStack([], {}, "Status")).toEqual([{ category: "Status" }]);
    expect(computeKpiStack(null, {}, "Status")).toEqual([
      { category: "Status" },
    ]);
  });

  test("two segments with scalar responses tally into single row", () => {
    const responses = {
      operational: { data: [{ value: 85 }] },
      issues: { data: [{ value: 16 }] },
    };
    expect(computeKpiStack(segments2, responses, "Operational Status")).toEqual(
      [
        {
          category: "Operational Status",
          Operational: 85,
          "Issues with the system": 16,
        },
      ]
    );
  });

  test("missing response → 0 for that segment", () => {
    const responses = {
      operational: { data: [{ value: 85 }] },
      // issues missing
    };
    expect(computeKpiStack(segments2, responses, "Status")).toEqual([
      {
        category: "Status",
        Operational: 85,
        "Issues with the system": 0,
      },
    ]);
  });

  test("empty data array → 0", () => {
    const responses = {
      operational: { data: [] },
      issues: { data: [{ value: 10 }] },
    };
    expect(computeKpiStack(segments2, responses, "Status")).toEqual([
      {
        category: "Status",
        Operational: 0,
        "Issues with the system": 10,
      },
    ]);
  });

  test("supports N=3 segments", () => {
    const segments3 = [
      { key: "a", label: "A" },
      { key: "b", label: "B" },
      { key: "c", label: "C" },
    ];
    const responses = {
      a: { data: [{ value: 1 }] },
      b: { data: [{ value: 2 }] },
      c: { data: [{ value: 3 }] },
    };
    expect(computeKpiStack(segments3, responses, "X")).toEqual([
      { category: "X", A: 1, B: 2, C: 3 },
    ]);
  });

  test("null responses object → all segments 0", () => {
    expect(computeKpiStack(segments2, null, "Status")).toEqual([
      {
        category: "Status",
        Operational: 0,
        "Issues with the system": 0,
      },
    ]);
  });

  test("defaults category when not provided", () => {
    const responses = { operational: { data: [{ value: 1 }] } };
    const out = computeKpiStack(segments2, responses);
    expect(typeof out[0].category).toBe("string");
  });
});
