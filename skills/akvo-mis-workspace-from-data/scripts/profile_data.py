#!/usr/bin/env python
"""Profile a CSV/Excel file for Akvo MIS modelling.

    python profile_data.py data.xlsx [more.csv ...] [--json out.json]

For every sheet it prints each column's inferred MIS question type, blanks,
distinct values and samples, then the structural hints that decide the MIS
design:

  * registration key - an ID column whose values repeat across rows (one
                   registration datapoint observed many times)
                   -> registration + monitoring forms
  * per-datapoint - columns constant within each key -> registration form;
                   the rest vary per row -> monitoring form
  * hierarchy    - place-like text columns where each child value maps to
                   exactly one parent value -> administration levels
  * geo          - lat/lng column pairs or "lat, lng" text
"""
import argparse
import json
import re
import sys

import pandas as pd

PLACE = re.compile(
    r"country|region|province|state|county|district|sub.?county|division|"
    r"location|ward|village|municipal|city|town|commune|atoll|island|"
    r"zone|area|parish|sector|cell|kebele|woreda|admin", re.I)
LAT = re.compile(r"^(lat|latitude|y|gps.?lat)$", re.I)
LNG = re.compile(r"^(lon|lng|long|longitude|x|gps.?lon(g)?)$", re.I)
PII = re.compile(r"phone|mobile|tel\b|e-?mail|national.?id|\bnin\b|passport|"
                 r"id.?number|respondent|head.?of|full.?name|dob|birth", re.I)
DERIVED = re.compile(r"%|percent|pct|ratio|rate\b|total|sum\b|average|"
                     r"\bavg\b|mean\b|calculated|formula", re.I)
DATE = re.compile(r"date|time|day|month|year|when|visit|period", re.I)
# "Site ID", "hh_no", "id_site", "WPID": an identifier, not a quantity
IDENT = re.compile(r"(^|[\s_.#-])(id|code|no|nr|ref|key)\.?$|"
                   r"^(id|code)([\s_.#-]|$)|(?-i:[A-Za-z]ID$)", re.I)


def blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def infer(col, s):
    v = s[~blank(s)]
    n = len(v)
    if n == 0:
        return "empty"
    st = v.astype(str).str.strip()
    if st.str.match(r"^-?\d+(\.\d+)?\s*[, ]\s*-?\d+(\.\d+)?$").mean() > .9:
        return "geo"
    num = pd.to_numeric(st.str.replace(",", ""), errors="coerce")
    if st.str.match(r"^\+?\d[\d\s-]{7,}$").mean() > .9 and \
            (st.str.startswith("+").mean() > .5 or PII.search(col)):
        return "input"  # phone-like: digits but not a quantity
    if num.notna().mean() > .95:
        if LAT.match(col) or LNG.match(col):
            return "geo-part"
        return "number"
    iso = st.str.match(r"^\d{4}-\d{1,2}-\d{1,2}([ T]|$)|"
                       r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$").mean() > .9
    if pd.api.types.is_datetime64_any_dtype(s) or iso or (
            DATE.search(col) and pd.to_datetime(
                st, errors="coerce").notna().mean() > .9):
        return "date"
    uniq = st.str.casefold().nunique()
    if st.str.contains(r"[;|]").mean() > .05:
        parts = st.str.split(r"\s*[;|]\s*").explode().str.casefold()
        if parts.nunique() <= 20:
            return "multiple_option"
    if uniq <= max(12, n * .05) and st.str.len().max() <= 60:
        return "option"
    if st.str.len().mean() > 60:
        return "text"
    return "input"


def numeric_id(col, s):
    """Whole numbers in a column named like an id: 1001, not a quantity."""
    if not IDENT.search(col) or DERIVED.search(col) or DATE.search(col):
        return False
    num = pd.to_numeric(s, errors="coerce")
    return num.notna().all() and (num % 1 == 0).all()


def registration_keys(df, types):
    """ID columns whose rows are repeated observations of one datapoint."""
    out = []
    for c in df.columns:
        s = df[c][~blank(df[c])].astype(str).str.strip()
        if types[c] != "input" and not (types[c] == "number"
                                        and numeric_id(c, s)):
            continue
        if len(s) < len(df) * .95:
            continue
        u = s.nunique()
        if 1 < u < len(s) and len(s) / u >= 1.5:
            out.append((c, u, round(len(s) / u, 1)))
    return out


def split_constant(df, key):
    g = df.groupby(df[key].astype(str).str.strip())
    const, varying = [], []
    for c in df.columns:
        if c == key:
            continue
        per = g[c].nunique(dropna=True)
        (const if (per <= 1).mean() > .95 else varying).append(c)
    return const, varying


def hierarchy(df, types):
    cands = [c for c in df.columns if types[c] in ("option", "input")
             and PLACE.search(c)]
    norm = {c: df[c].astype(str).str.strip().str.casefold() for c in cands}
    edges = []
    for child in cands:
        for parent in cands:
            if child == parent:
                continue
            m = pd.DataFrame({"c": norm[child], "p": norm[parent]})
            m = m[~m.c.isin(["", "nan"]) & ~m.p.isin(["", "nan"])]
            if m.empty or m.c.nunique() <= m.p.nunique():
                continue
            if (m.groupby("c").p.nunique() <= 1).mean() > .97:
                edges.append((parent, child))
    # order into chains: parents first
    depth = {c: 0 for c in cands}
    for _ in cands:
        for p, c in edges:
            depth[c] = max(depth[c], depth[p] + 1)
    chain = sorted({c for e in edges for c in e}, key=lambda c: depth[c])
    return chain, edges


def geo_pairs(df, types):
    lat = [c for c in df.columns if LAT.match(c.strip())]
    lng = [c for c in df.columns if LNG.match(c.strip())]
    pairs = [(a, b) for a in lat for b in lng]
    pairs += [(c,) for c in df.columns if types[c] == "geo"]
    return pairs


def case_variants(s):
    st = s[~blank(s)].astype(str).str.strip()
    groups = st.groupby(st.str.casefold()).unique()
    return {k: list(v) for k, v in groups.items() if len(v) > 1}


def profile(path, sheet, df):
    df = df.dropna(how="all")
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    types = {c: infer(c, df[c]) for c in df.columns}
    res = {"file": path, "sheet": sheet, "rows": len(df), "columns": []}
    for c in df.columns:
        s = df[c]
        v = s[~blank(s)].astype(str).str.strip()
        info = {"name": c, "type": types[c], "blank": int(blank(s).sum()),
                "distinct": int(v.nunique())}
        if types[c] in ("option", "multiple_option"):
            vals = v.str.split(r"\s*[;|]\s*").explode() \
                if types[c] == "multiple_option" else v
            info["values"] = vals.value_counts().head(25).to_dict()
        else:
            info["samples"] = v.drop_duplicates().head(4).tolist()
        if types[c] == "number":
            n = pd.to_numeric(v.str.replace(",", ""), errors="coerce")
            info["min"], info["max"] = float(n.min()), float(n.max())
            info["decimal"] = bool((n.dropna() % 1 != 0).any())
        flags = []
        if PII.search(c) or v.str.match(r"^\+\d{9,}$").mean() > .5:
            flags.append("PERSONAL DATA? ask before loading")
        if DERIVED.search(c) or v.str.endswith("%").mean() > .5:
            flags.append("DERIVED? usually not loaded; chart it instead")
        if types[c] == "date" and v.str.match(
                r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$").mean() > .5:
            flags.append("day/month order ambiguous: set date_format")
        if flags:
            info["flags"] = flags
        cv = case_variants(s) if types[c] in ("option", "input") else {}
        if cv:
            info["case_variants"] = dict(list(cv.items())[:5])
        res["columns"].append(info)
    keys = registration_keys(df, types)
    res["registration_keys"] = []
    for c, u, ratio in keys:
        const, varying = split_constant(df, c)
        res["registration_keys"].append({"column": c, "datapoints": u,
                                   "rows_per_datapoint": ratio,
                                   "constant_per_datapoint": const,
                                   "varying": varying})
    chain, edges = hierarchy(df, types)
    res["hierarchy"] = {"chain": chain, "edges": edges}
    res["geo"] = geo_pairs(df, types)
    uniq_cols = [c for c in df.columns
                 if df[c].notna().all() and df[c].astype(str).nunique()
                 == len(df) and types[c] == "input"
                 and not PII.search(c) and not DERIVED.search(c)]
    res["unique_columns"] = uniq_cols
    return res


def cross_links(results):
    """Key columns of one sheet whose values another sheet's rows reuse."""
    links = []
    for a in results:
        for key in a["unique_columns"]:
            ids = set(a["_df"][key].astype(str).str.strip())
            for b in results:
                if b is a:
                    continue
                for col in b["_df"].columns:
                    vals = b["_df"][col].dropna().astype(str).str.strip()
                    if len(vals) and vals.isin(ids).mean() > .9 \
                            and vals.nunique() < len(vals):
                        links.append((f"{a['sheet']}.{key}",
                                      f"{b['sheet']}.{col}"))
    return links


def show(r):
    print(f"\n## {r['file']} :: {r['sheet']}  ({r['rows']} rows)")
    for c in r["columns"]:
        extra = c.get("values") or c.get("samples")
        rng = f" range {c['min']:g}..{c['max']:g}" if "min" in c else ""
        print(f"- {c['name']!r}: {c['type']}, {c['blank']} blank, "
              f"{c['distinct']} distinct{rng} | {str(extra)[:160]}")
        for fl in c.get("flags", []):
            print(f"    ! {fl}")
        if c.get("case_variants"):
            print(f"    ! spelling/case variants: {c['case_variants']}")
    print(f"unique per row (candidate record id): {r['unique_columns']}")
    for k in r["registration_keys"]:
        print(f"registration key {k['column']!r}: {k['datapoints']} "
              f"datapoints, {k['rows_per_datapoint']} rows each")
        print(f"    constant per datapoint -> registration form: "
              f"{k['constant_per_datapoint']}")
        print(f"    varying per row        -> monitoring form:   "
              f"{k['varying']}")
    if r["hierarchy"]["chain"]:
        print(f"administration chain (top -> bottom): "
              f"{r['hierarchy']['chain']}")
    if r["geo"]:
        print(f"geo: {r['geo']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args()
    out = []
    for f in a.files:
        if f.lower().endswith((".xlsx", ".xlsm", ".xls")):
            sheets = pd.read_excel(f, sheet_name=None, dtype=object,
                                   keep_default_na=False, na_values=[""])
        else:
            sheets = {"csv": pd.read_csv(f, dtype=object,
                                         encoding="utf-8-sig",
                                         sep=None, engine="python",
                                         keep_default_na=False,
                                         na_values=[""])}
        for name, df in sheets.items():
            if df.dropna(how="all").empty:
                continue
            r = profile(f, name, df)
            r["_df"] = df
            show(r)
            out.append(r)
    links = cross_links(out)
    if links:
        print("\n## links between sheets (registration -> monitoring)")
        for a_, b_ in links:
            print(f"- {a_} is referenced by {b_}")
    for r in out:
        r.pop("_df", None)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=2, default=str)


if __name__ == "__main__":
    sys.exit(main())
