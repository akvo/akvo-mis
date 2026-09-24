import { formatApiDateTime, getDateRange, timeDiffHours } from "../date";

describe("App", () => {
  test("test if getDateRange is return correct value", () => {
    const dateTest = getDateRange({
      startDate: "20221101",
      endDate: "20230104",
    });
    expect(dateTest).toStrictEqual(["November 01, 2022", "December 01, 2022"]);
  });

  test("test timeDiffHours", () => {
    expect(timeDiffHours(1657280905.183572)).toBeDefined();
  });
});

describe("formatApiDateTime", () => {
  /**
   * The API renders `%d-%m-%Y %H:%M:%S`. `new Date()` reads that month-first, which fails in
   * two different ways — and the loud one is the safe one.
   */
  test("reads the day first, not the month", () => {
    // `new Date("11-09-2026 23:19:34")` returned 9 NOVEMBER: a plausible wrong date, shown
    // without an error, two months adrift. That is the half that needs a test.
    const parsed = new Date(formatApiDateTime("11-09-2026 23:19:34"));
    expect(formatApiDateTime("11-09-2026 23:19:34")).not.toMatch(/Invalid/);
    expect(parsed.getMonth()).toBe(8); // September, zero-indexed
    expect(parsed.getDate()).toBe(11);
  });

  test("parses a day past the 12th, which used to be Invalid Date", () => {
    const parsed = new Date(formatApiDateTime("15-09-2026 00:15:37"));
    expect(parsed.getMonth()).toBe(8);
    expect(parsed.getDate()).toBe(15);
  });

  test("falls back rather than guessing", () => {
    expect(formatApiDateTime(null)).toBe("—");
    expect(formatApiDateTime("")).toBe("—");
    expect(formatApiDateTime("not a date")).toBe("—");
    // Ambiguous separator, deliberately refused: strict parsing is what stops a wrong date
    // from looking like a right one.
    expect(formatApiDateTime("11/09/2026")).toBe("—");
    expect(formatApiDateTime(null, "n/a")).toBe("n/a");
  });

  test("also accepts ISO, so dropping DATETIME_FORMAT later improves this rather than breaking it", () => {
    const parsed = new Date(formatApiDateTime("2026-09-11T23:19:34Z"));
    expect(parsed.getUTCMonth()).toBe(8);
    expect(parsed.getUTCDate()).toBe(11);
  });
});
