"""Read an uploaded spreadsheet and profile its columns.

The profile is all OpenAI ever sees of the file (ADR 0001). Only
category-like columns (at most CATEGORY_LIMIT distinct values, and no
more distinct values than half the filled cells) carry their values;
every other column carries a value shape and counts.
"""
import csv
import re

import pandas as pd

from api.v1.v1_data_onboarding.places import norm, text

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_ROWS = 50_000
CATEGORY_LIMIT = 30

GEO = re.compile(r"-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?")
NUMBER = re.compile(r"-?\d+(\.\d+)?")
DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}([ T].*)?|\d{1,2}/\d{1,2}/\d{2,4}")


class OnboardingError(ValueError):
    """A failure whose message is safe to show the user."""


def extension(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def read_sheets(path, name):
    """Return {sheet name: DataFrame of str-or-None cells}."""
    ext = extension(name)
    if ext not in ("csv", "xlsx"):
        raise OnboardingError("Upload a CSV or xlsx file.")
    # Only empty cells are blank: NA, None, - stay values.
    opts = {"dtype": object, "keep_default_na": False, "na_values": [""]}
    try:
        if ext == "csv":
            with open(path, encoding="utf-8-sig", newline="") as fh:
                sample = fh.read(64 * 1024)
            try:
                sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                sep = ","  # a single column has no delimiter to find
            sheets = {
                "csv": pd.read_csv(
                    path, sep=sep, encoding="utf-8-sig", **opts
                )
            }
        else:
            sheets = pd.read_excel(path, sheet_name=None, **opts)
    except Exception:
        raise OnboardingError(f"The file could not be read as {ext}.")
    result = {}
    for sheet, df in sheets.items():
        df = df.dropna(how="all")
        df.columns = [norm(c) for c in df.columns]
        result[str(sheet)] = df.astype(object).where(df.notna(), None)
    return result


def check_rows(sheets):
    if sum(len(df) for df in sheets.values()) > MAX_ROWS:
        raise OnboardingError(
            f"The file has more than {MAX_ROWS:,} rows. Trim it and retry."
        )


def _is_number(v):
    # Leading zeros (phone numbers, codes) are not quantities.
    return bool(NUMBER.fullmatch(v)) and not (
        len(v) > 1 and v[0] == "0" and v[1] != "."
    )


def _infer(values, distinct):
    n = len(values)

    def share(pred):
        return sum(1 for v in values if pred(v)) / n

    if not n:
        return "empty"
    if share(GEO.fullmatch) > 0.9:
        return "geo"
    if share(_is_number) > 0.95:
        return "number"
    if share(DATE.fullmatch) > 0.9:
        return "date"
    if share(lambda v: re.search(r"[;|]", v)) > 0.05:
        parts = {p.strip() for v in values for p in re.split(r"[;|]", v)}
        if len(parts) <= 20:
            return "multiple_option"
    if distinct <= CATEGORY_LIMIT and max(map(len, values)) <= 60:
        return "option"
    return "text" if sum(map(len, values)) / n > 60 else "input"


def _kind(v):
    if v.isdigit():
        return "digits"
    if re.fullmatch(r"[^\W\d_]+", v):
        return "letters"
    if re.fullmatch(r"\w+", v):
        return "letters and digits"
    return "characters"


def _shape(values):
    """Describe values without repeating any, e.g. '10 digits'."""
    if not values:
        return "empty"
    kinds = {_kind(v) for v in values}
    kind = kinds.pop() if len(kinds) == 1 else "characters"
    lo, hi = min(map(len, values)), max(map(len, values))
    return f"{lo} {kind}" if lo == hi else f"{lo}-{hi} {kind}"


def profile_sheets(sheets):
    result = []
    for sheet, df in sheets.items():
        columns = []
        for name in df.columns:
            values = [text(v) for v in df[name] if v is not None]
            values = [v for v in values if v]
            distinct = sorted(set(values))
            column = {
                "name": name,
                "type": _infer(values, len(distinct)),
                "filled": len(values),
                "blank": len(df) - len(values),
                "distinct": len(distinct),
                "shape": _shape(values),
            }
            # Unique-per-row columns (names, IDs) never send values.
            if (
                len(distinct) <= CATEGORY_LIMIT
                and len(distinct) * 2 <= len(values)
            ):
                column["values"] = distinct
            columns.append(column)
        result.append({"name": sheet, "rows": len(df), "columns": columns})
    return {"sheets": result}
