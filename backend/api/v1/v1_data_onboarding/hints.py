"""Structural hints for the column profile, ported from #462's profiler.

They tell OpenAI what code can measure but a column list cannot show:
which ID column repeats (one record seen many times: registration plus
monitoring), which place columns nest, which columns pair as lat/lng,
which column of one sheet holds another sheet's keys, and which columns
look personal or derived. Hints name columns and give counts only,
never cell values (ADR 0001), and a personal column sends no values
even when they repeat.
"""
import re

from api.v1.v1_data_onboarding.places import fold, text

PLACE = re.compile(
    r"country|region|province|state|county|district|sub.?county|division|"
    r"location|ward|village|municipal|city|town|commune|atoll|island|"
    r"zone|area|parish|sector|cell|kebele|woreda|admin", re.I)
LAT = re.compile(r"^(lat|latitude|y|gps.?lat)$", re.I)
LNG = re.compile(r"^(lon|lng|long|longitude|x|gps.?lon(g)?)$", re.I)
# Columns that identify a person. Not "respondent" or "head of":
# respondent_gender is a category, and its values are needed.
PERSONAL = re.compile(
    r"phone|mobile|(?<![a-z])tel(?![a-z])|e-?mail|national.?id|\bnin\b|"
    r"passport|id.?number|full.?name|(?<![a-z])dob(?![a-z])|birth", re.I)
DERIVED = re.compile(r"%|percent|pct|ratio|rate\b|total|sum\b|average|"
                     r"\bavg\b|mean\b|calculated|formula", re.I)
DATE = re.compile(r"date|time|day|month|year|when|visit|period", re.I)
# "Site ID", "hh_no", "id_site", "WPID": an identifier, not a quantity
IDENT = re.compile(r"(^|[\s_.#-])(id|code|no|nr|ref|key)\.?$|"
                   r"^(id|code)([\s_.#-]|$)|(?-i:[A-Za-z]ID$)", re.I)
DAY_MONTH = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")
PHONE = re.compile(r"\+\d{9,}")


def _cells(df, column):
    return [text(v) for v in df[column]]


def _filled(cells):
    return [c for c in cells if c]


def _flags(name, kind, values):
    n = len(values) or 1
    flags = []
    if PERSONAL.search(name) or \
            sum(1 for v in values if PHONE.fullmatch(v)) / n > .5:
        flags.append("personal")
    if DERIVED.search(name) or \
            sum(1 for v in values if v.endswith("%")) / n > .5:
        flags.append("derived")
    if kind == "date" and \
            sum(1 for v in values if DAY_MONTH.fullmatch(v)) / n > .5:
        flags.append("day_month_order")
    return flags


def _id_like(name, kind, values):
    """A column that identifies records, whatever type it was given.

    Free text is a candidate as is. A column named like an id also
    counts when few distinct values made it look like an option list
    (10 sites over 100 visits), or when its values are whole numbers.
    """
    if kind == "input":
        return True
    if not IDENT.search(name) or DERIVED.search(name) or DATE.search(name):
        return False
    if kind == "option":
        return True
    return kind == "number" and all(re.fullmatch(r"-?\d+", v)
                                    for v in values)


def _registration_keys(df, kinds):
    rows = len(df)
    keys = []
    for name in df.columns:
        cells = _cells(df, name)
        values = _filled(cells)
        if len(values) < rows * .95 or \
                not _id_like(name, kinds[name], values):
            continue
        distinct = len(set(values))
        if not 1 < distinct < len(values) or len(values) / distinct < 1.5:
            continue
        per_key = {}
        for i, key in enumerate(cells):
            if key:
                per_key.setdefault(key, []).append(i)
        constant, varying = [], []
        for other in df.columns:
            if other == name:
                continue
            col = _cells(df, other)
            same = sum(1 for idx in per_key.values()
                       if len({col[i] for i in idx if col[i]}) <= 1)
            (constant if same / len(per_key) > .95 else varying).append(
                other)
        keys.append({
            "column": name, "records": distinct,
            "rows_per_record": round(len(values) / distinct, 1),
            "constant_per_record": constant, "varying": varying,
        })
    return keys


def _hierarchy(df, kinds):
    """Place columns that nest, parent first."""
    places = [c for c in df.columns
              if kinds[c] in ("option", "input") and PLACE.search(c)]
    folded = {c: [fold(v) if v else "" for v in _cells(df, c)]
              for c in places}
    edges = []
    for child in places:
        for parent in places:
            if child == parent:
                continue
            pairs = [(c, p) for c, p in zip(folded[child], folded[parent])
                     if c and p]
            children = {c for c, _ in pairs}
            if not pairs or len(children) <= len({p for _, p in pairs}):
                continue
            parents_of = {}
            for c, p in pairs:
                parents_of.setdefault(c, set()).add(p)
            single = sum(1 for ps in parents_of.values() if len(ps) == 1)
            if single / len(parents_of) > .97:
                edges.append((parent, child))
    depth = {c: 0 for c in places}
    for _ in places:
        for parent, child in edges:
            depth[child] = max(depth[child], depth[parent] + 1)
    return sorted({c for edge in edges for c in edge}, key=depth.get)


def _geo(df, kinds):
    lat = [c for c in df.columns if LAT.match(c)]
    lng = [c for c in df.columns if LNG.match(c)]
    pairs = [{"lat": a, "lng": b} for a in lat for b in lng]
    return pairs + [{"column": c} for c in df.columns if kinds[c] == "geo"]


def _links(sheets, profiles):
    """A column whose values are mostly another sheet's unique keys."""
    links = []
    for a, df in sheets.items():
        kinds = {c["name"]: c["type"] for c in profiles[a]["columns"]}
        for key in df.columns:
            values = _cells(df, key)
            if not all(values) or len(set(values)) != len(values) or \
                    not _id_like(key, kinds[key], values):
                continue
            ids = set(values)
            for b, other in sheets.items():
                if b == a:
                    continue
                for col in other.columns:
                    vals = _filled(_cells(other, col))
                    if vals and len(set(vals)) < len(vals) and \
                            sum(1 for v in vals if v in ids) / len(vals) > .9:
                        links.append({"keys": f"{a}.{key}",
                                      "column": f"{b}.{col}"})
    return links


def add_hints(sheets, profile):
    """Add hints to a profile_sheets() result in place, and return it."""
    profiles = {s["name"]: s for s in profile["sheets"]}
    for name, df in sheets.items():
        sheet = profiles[name]
        kinds = {c["name"]: c["type"] for c in sheet["columns"]}
        for column in sheet["columns"]:
            flags = _flags(column["name"], column["type"],
                           _filled(_cells(df, column["name"])))
            if flags:
                column["flags"] = flags
            if "personal" in flags:
                column.pop("values", None)  # repeats, but still personal
        sheet["registration_keys"] = _registration_keys(df, kinds)
        sheet["hierarchy"] = _hierarchy(df, kinds)
        sheet["geo"] = _geo(df, kinds)
    profile["links"] = _links(sheets, profiles)
    return profile
