#!/usr/bin/env python
"""Akvo MIS workspace client: sign up, configure, seed and load over HTTP.

Standard library only for the HTTP side; pandas (+ openpyxl for .xlsx) is
needed only by `load-data`, to read the source spreadsheet.

Every command reads the approved plan (plan.json) and a state file
(mis-state.json, created next to the plan, chmod 600) that holds the
connection, the temporary password, the session token and the ids the
server handed back. Every step is idempotent: re-running it skips what
already exists, so a failure half way is fixed by re-running.

    python mis.py --plan plan.json check
    python mis.py --plan plan.json register          # emails an activation link
    python mis.py --plan plan.json login             # after the user activated
    python mis.py --plan plan.json configure
    python mis.py --plan plan.json seed-admin [--dry-run]
    python mis.py --plan plan.json seed-forms [--dry-run]
    python mis.py --plan plan.json load-data  [--dry-run] [--only FORM_KEY]
    python mis.py --plan plan.json status
    python mis.py --plan plan.json apply              # login..load-data in order

Local testing against a docker stack (BASE_DOMAIN=app.local on :8000):
    --connect http://localhost:8000  sends every request there and puts the
    real workspace host in the Host header instead.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuidlib

UUID_NS = uuidlib.UUID("6f1c2b1e-2d4b-4a7e-9d0c-6d1a4b1f0a11")
KNOWN_BASES = ("mis.akvotest.org", "mis.akvo.org")
LOOPBACK = ("localhost", "127.0.0.1", "::1")
LOCAL_BASE = "app.local"  # the docker stack's BASE_DOMAIN; needs --connect


def target_problem(ws, connect=None):
    """Why the plan must not send credentials where it points, or None.

    Only the known MIS domains over HTTPS, unless --connect sends the
    requests to a local docker stack (the documented testing path).
    """
    if connect:
        u = urllib.parse.urlsplit(connect)
        if u.scheme == "https" or (u.scheme == "http"
                                   and u.hostname in LOOPBACK):
            return None
        return (f"--connect {connect}: use https, or http only to "
                f"{'/'.join(LOOPBACK)}")
    if ws.get("base_domain") not in KNOWN_BASES:
        return (f"base_domain '{ws.get('base_domain')}' is not one of "
                f"{', '.join(KNOWN_BASES)} (for a local docker stack, pass "
                f"--connect http://localhost:8000)")
    if ws.get("scheme", "https") != "https":
        return f"scheme must be https for {ws['base_domain']}"
    return None


# --------------------------------------------------------------------- state

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


class Ctx:
    def __init__(self, args):
        self.args = args
        self.plan_path = os.path.abspath(args.plan)
        self.plan = load_json(self.plan_path)
        if self.plan is None:
            sys.exit(f"plan not found: {self.plan_path}")
        self.plan_dir = os.path.dirname(self.plan_path)
        self.state_path = args.state or os.path.join(
            self.plan_dir, "mis-state.json")
        self.state = load_json(self.state_path, {}) or {}
        ws = self.plan["workspace"]
        self.sub = ws["subdomain"]
        self.base = ws["base_domain"]
        self.scheme = ws.get("scheme", "https")
        self.connect = args.connect or self.state.get("connect")
        if args.connect:
            self.state["connect"] = args.connect
        bad = target_problem(ws, self.connect)
        if bad:
            sys.exit(f"refusing to connect: {bad}")
        self.state.setdefault("subdomain", self.sub)
        if self.state["subdomain"] != self.sub:
            sys.exit(f"state file belongs to workspace "
                     f"'{self.state['subdomain']}', plan says '{self.sub}'. "
                     f"Use --state to point at another state file.")

    def save(self):
        save_state(self.state_path, self.state)

    def path(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.plan_dir, rel)

    # ------------------------------------------------------------- http
    def host(self, workspace=True):
        return f"{self.sub}.{self.base}" if workspace else self.base

    def request(self, method, path, body=None, workspace=True, auth=True,
                retry_auth=True):
        host = self.host(workspace)
        root = self.connect.rstrip("/") if self.connect \
            else f"{self.scheme}://{host}"
        url = f"{root}/api/v1/{path.lstrip('/')}"
        data = None
        headers = {"Accept": "application/json",
                   "User-Agent": "akvo-mis-workspace-skill/1.0"}
        if self.connect:
            headers["Host"] = host
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if auth and self.state.get("token"):
            headers["Authorization"] = f"Bearer {self.state['token']}"
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            status = e.code
        except urllib.error.URLError as e:
            sys.exit(f"cannot reach {url}: {e.reason}\n"
                     f"If this runs in a sandbox without internet access, "
                     f"run the same command on your own computer instead.")
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = {"raw": raw[:500].decode(errors="replace")}
        if status == 401 and auth and retry_auth and self.state.get("password"):
            self._login(quiet=True)
            return self.request(method, path, body, workspace, auth, False)
        return status, payload

    def ok(self, method, path, body=None, expect=(200, 201), **kw):
        status, payload = self.request(method, path, body, **kw)
        if status not in expect:
            raise ApiError(method, path, status, payload)
        return payload

    def _login(self, quiet=False):
        status, p = self.request(
            "POST", "login",
            {"email": self.plan["workspace"]["email"],
             "password": self.state["password"]},
            auth=False)
        if status != 200:
            if p and p.get("unverified"):
                sys.exit("The account is not activated yet. Ask the user to "
                         "click the activation link in their email "
                         "(check spam), then run `login` again.")
            sys.exit(f"login failed ({status}): {p}")
        self.state["token"] = p["token"]
        self.state["token_at"] = int(time.time())
        self.state["configured"] = p.get("configured")
        self.save()
        if not quiet:
            print(f"logged in to {self.host()} as {p.get('email')} "
                  f"(super admin: {p.get('is_superuser')}, "
                  f"configured: {p.get('configured')})")
        return p

    def paged(self, path):
        page, out = 1, []
        sep = "&" if "?" in path else "?"
        while True:
            p = self.ok("GET", f"{path}{sep}page={page}&page_size=100")
            if isinstance(p, list):
                return p
            out.extend(p.get("data", []))
            if page >= int(p.get("total_page") or 1):
                return out
            page += 1


class ApiError(Exception):
    def __init__(self, method, path, status, payload):
        super().__init__(f"{method} {path} -> {status}: "
                         f"{json.dumps(payload)[:800]}")
        self.status = status
        self.payload = payload


# ------------------------------------------------------------ signup / auth

def gen_password():
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"Mis-{core}#1"


def cmd_check(ctx):
    s, p = ctx.request("GET", "health/check", workspace=False, auth=False)
    print(f"base domain {ctx.host(False)}: health {s}")
    s, p = ctx.request("GET", "tenant-info", auth=False)
    if s == 404:
        print(f"workspace {ctx.host()}: does not exist yet (subdomain free)")
    elif s == 200:
        print(f"workspace {ctx.host()}: EXISTS ({p}). Pick another "
              f"subdomain unless this is the user's own workspace.")
    elif s == 204:
        print(f"STOP: {ctx.host()} is treated as the base domain, so this "
              f"server has no subdomain routing (BASE_DOMAIN unset) or the "
              f"base_domain in the plan is wrong. Workspaces cannot be "
              f"created here.")
    else:
        print(f"workspace {ctx.host()}: unexpected {s} {p}")
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", ctx.sub) \
            or len(ctx.sub) > 63:
        print("WARNING: subdomain must be lowercase letters, digits and "
              "inner hyphens, max 63 chars")


def cmd_register(ctx):
    ws = ctx.plan["workspace"]
    if ctx.state.get("registered"):
        print("already registered; the user must click the activation link "
              "(re-send with `resend-activation`)")
        return
    ctx.state.setdefault("password", gen_password())
    ctx.save()
    status, p = ctx.request(
        "POST", "register",
        {"email": ws["email"], "password": ctx.state["password"],
         "subdomain": ctx.sub},
        workspace=False, auth=False)
    if status != 200:
        sys.exit(f"register failed ({status}): {p}")
    ctx.state["registered"] = True
    ctx.save()
    print(f"registered {ctx.host()} for {ws['email']}")
    print(f"temporary password: {ctx.state['password']}")
    print("An activation email is on its way. The user must click the link "
          "in it (valid 7 days), then run `login`.")


def cmd_resend(ctx):
    s, p = ctx.request("POST", "register/resend-activation",
                       {"email": ctx.plan["workspace"]["email"]}, auth=False)
    print(s, p)


def cmd_activate(ctx):
    token = ctx.args.token.rstrip("/").split("/activate/")[-1]
    s, p = ctx.request("POST", "register/activate", {"token": token},
                       auth=False)
    if s != 200:
        sys.exit(f"activation failed ({s}): {p}")
    ctx.state["token"] = p["token"]
    ctx.state["token_at"] = int(time.time())
    ctx.save()
    print("activated")


def cmd_login(ctx):
    if not ctx.state.get("password"):
        pw = os.environ.get("MIS_PASSWORD")
        if not pw:
            sys.exit("no password in state; set MIS_PASSWORD for an "
                     "existing account")
        ctx.state["password"] = pw
    ctx._login()


def ensure_login(ctx):
    # Tokens live 12h but the profile check expires after 4h idle; re-login
    # past 3h so a long load never trips over it.
    if not ctx.state.get("token") or \
            time.time() - ctx.state.get("token_at", 0) > 3 * 3600:
        ctx._login(quiet=True)


def cmd_configure(ctx):
    ensure_login(ctx)
    ws, adm = ctx.plan["workspace"], ctx.plan["administration"]
    status, p = ctx.request("POST", "register/configure", {
        "first_name": ws.get("first_name") or "Workspace",
        "last_name": ws.get("last_name") or "Admin",
        "level_0_name": adm["levels"][0],
        "root_unit_name": adm["root"],
    })
    if status == 200:
        print(f"configured: level 0 '{adm['levels'][0]}', "
              f"root '{adm['root']}'")
    elif status == 400 and "already configured" in json.dumps(p):
        print("already configured")
    else:
        sys.exit(f"configure failed ({status}): {p}")


# ------------------------------------------------------------ administration

def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def lookup(mapping, raw):
    """mapping[raw], matched ignoring case and surrounding whitespace."""
    want = norm(raw).casefold()
    for k, v in (mapping or {}).items():
        if norm(k).casefold() == want:
            return v
    return raw


def key_of(path):
    return "|".join(norm(x).casefold() for x in path)


def read_table(ctx, spec):
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas is required to read the data file: "
                 "pip install pandas openpyxl")
    f = ctx.path(spec["file"])
    if f.lower().endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(f, sheet_name=spec.get("sheet") or 0, dtype=object,
                           header=spec.get("header_row", 0),
                           keep_default_na=False, na_values=[""])
    else:
        # no "sep" in the spec: sniff it, as profile_data.py does
        df = pd.read_csv(f, dtype=object, sep=spec.get("sep"),
                         engine="python", header=spec.get("header_row", 0),
                         encoding=spec.get("encoding", "utf-8-sig"),
                         keep_default_na=False, na_values=[""])
    df.columns = [norm(c) for c in df.columns]
    df = df.dropna(how="all")
    return df.where(df.notna(), None)


def blank(v):
    return v is None or (isinstance(v, float) and v != v) or \
        (isinstance(v, str) and not v.strip())


def admin_units(ctx):
    """All administration paths (below the root) the plan asks for."""
    adm = ctx.plan["administration"]
    paths = [tuple(norm(x) for x in p) for p in adm.get("units", [])]
    sources = list(adm.get("sources", []))
    if adm.get("source"):
        sources.append(adm["source"])
    for src in sources:
        df = read_table(ctx, src)
        aliases = adm.get("aliases", {})
        for row in df[src["columns"]].itertuples(index=False):
            vals = [norm(lookup(aliases, v)) for v in row if not blank(v)]
            if len(vals) != len(src["columns"]):
                continue  # incomplete path; load-data reports these rows
            paths.append(tuple(vals))
    out, seen = [], set()
    for p in paths:
        for i in range(1, len(p) + 1):
            k = key_of(p[:i])
            if k not in seen:
                seen.add(k)
                out.append(p[:i])
    return out


def fetch_admin_index(ctx):
    rows = ctx.paged("administrations")
    by_id = {r["id"]: r for r in rows}
    root = None

    def parent_id(r):
        par = r.get("parent")
        return par.get("id") if isinstance(par, dict) else par

    idx = {}
    for r in rows:
        chain, cur = [], r
        while cur is not None:
            pid = parent_id(cur)
            if pid is None:
                root = cur
                break
            chain.append(cur["name"])
            cur = by_id.get(pid)
        idx[key_of(reversed(chain))] = r["id"]
    return root, idx


def cmd_seed_admin(ctx):
    ensure_login(ctx)
    levels = ctx.plan["administration"]["levels"]
    existing = ctx.ok("GET", "levels-management")
    have = {lv["level"]: lv for lv in existing}
    units = admin_units(ctx)
    depth = max((len(u) for u in units), default=0)
    if depth > len(levels) - 1:
        sys.exit(f"data has {depth} levels below the root but the plan "
                 f"names only {len(levels) - 1}")
    root, idx = fetch_admin_index(ctx)
    for n, name in enumerate(levels):
        if n in have:
            if norm(have[n]["name"]) != norm(name):
                print(f"level {n} is '{have[n]['name']}' "
                      f"(plan says '{name}'), renaming")
                if not ctx.args.dry_run:
                    ctx.ok("PUT", f"levels-management/{have[n]['id']}",
                           {"name": name})
            continue
        print(f"+ level {n}: {name}")
        if not ctx.args.dry_run:
            ctx.ok("POST", "levels-management", {"name": name})
    if root is None:
        sys.exit("no root administration: run `configure` first")
    ids = {"": root["id"]}
    ids.update(idx)
    created = 0
    for path in sorted(units, key=len):
        k = key_of(path)
        if k in ids:
            continue
        parent = ids.get(key_of(path[:-1]))
        print(f"+ {' > '.join(path)}")
        created += 1
        if ctx.args.dry_run:
            ids[k] = -1
            continue
        p = ctx.ok("POST", "administrations",
                   {"name": path[-1], "parent": parent})
        ids[k] = p["id"]
    print(f"administration: {len(units)} units below the root in plan, "
          f"{created} "
          f"{'to create' if ctx.args.dry_run else 'created'}")


# --------------------------------------------------------------------- forms

QTYPE = {"input": "input", "text": "text", "number": "number",
         "date": "date", "option": "option",
         "multiple_option": "multiple_option", "geo": "geo",
         "photo": "image", "image": "image", "signature": "signature",
         "attachment": "attachment", "administration": "cascade"}


def option_value(label):
    v = re.sub(r"[^0-9a-z]+", "_", str(label).strip().lower()).strip("_")
    return v or "option"


def value_collisions(labels):
    """Labels that turn into the same stored value, e.g. 'A/B' and 'A B'."""
    by_value = {}
    for o in labels:
        by_value.setdefault(option_value(o), []).append(o)
    return [v for v in by_value.values() if len(v) > 1]


def form_problems(form):
    """Plan errors the server would reject with an integrity error."""
    out = []
    clash = value_collisions(g["label"] for g in form["groups"])
    if clash:
        out.append(f"form {form['key']}: group labels {clash} are the same "
                   f"once simplified; rename them")
    for q in plan_questions(form):
        clash = value_collisions(q.get("options") or [])
        if clash:
            out.append(f"{form['key']}.{q['name']}: options {clash} are the "
                       f"same once simplified; merge or rename them")
    return out


def question_payload(q, order):
    t = q["type"]
    if t not in QTYPE:
        sys.exit(f"question '{q['name']}': unsupported type '{t}' "
                 f"(use one of {', '.join(QTYPE)})")
    out = {"order": order, "name": q["name"], "label": q["label"],
           "type": QTYPE[t], "required": bool(q.get("required", False)),
           "meta": bool(q.get("meta", False)),
           "dependency_rule": "AND"}
    if q.get("tooltip"):
        out["tooltip"] = {"text": q["tooltip"]}
    if t == "administration":
        out["extra"] = {"type": "administration"}
    if t in ("option", "multiple_option"):
        out["option"] = [{"label": o, "value": option_value(o), "order": i}
                         for i, o in enumerate(q["options"], 1)]
    if t == "number":
        rule = {k: q[k] for k in ("min", "max") if q.get(k) is not None}
        rule["allowDecimal"] = bool(q.get("decimal", True))
        out["rule"] = rule
    return out


def form_payload(form, parent_id=None):
    groups = []
    for gi, g in enumerate(form["groups"], 1):
        groups.append({
            "name": option_value(g["label"]), "label": g["label"],
            "order": gi, "repeatable": False,
            "question": [question_payload(q, qi)
                         for qi, q in enumerate(g["questions"], 1)],
        })
    body = {"name": form["name"],
            "description": form.get("description", ""),
            "type": 2 if form["type"] == "monitoring" else 1,
            "question_group": groups}
    if parent_id:
        body["parent"] = parent_id
    return body


def plan_questions(form):
    return [q for g in form["groups"] for q in g["questions"]]


def apply_dependencies(form, editor):
    """Put `depends_on` into the server's editor copy, by question name."""
    ids = {q["name"]: q["id"]
           for g in editor["question_group"] for q in g["question"]}
    wanted = {q["name"]: q["depends_on"] for q in plan_questions(form)
              if q.get("depends_on")}
    for g in editor["question_group"]:
        for q in g["question"]:
            dep = wanted.get(q["name"])
            if dep:
                q["dependency"] = [{
                    "id": ids[dep["question"]],
                    "options": [option_value(v) for v in dep["values"]],
                }]
    return bool(wanted)


def find_form(ctx, name, ftype):
    for f in ctx.paged(f"manage/forms?type={ftype}"):
        if norm(f["name"]).casefold() == norm(name).casefold():
            return f
        for c in f.get("children") or []:
            if norm(c["name"]).casefold() == norm(name).casefold():
                return c
    return None


def existing_form(ctx, key, form):
    """Server copy of the plan's form, by the id in state or by name."""
    known = ctx.state.get("forms", {}).get(key, {}).get("id")
    if known:
        s, detail = ctx.request("GET", f"manage/forms/{known}")
        if s == 200:
            return detail
        if s != 404:
            raise ApiError("GET", f"manage/forms/{known}", s, detail)
    found = find_form(ctx, form["name"], form["type"])
    return ctx.ok("GET", f"manage/forms/{found['id']}") if found else None


def form_mismatch(form, detail, parent_id):
    """Why the server's form is not the one the plan describes, or None."""
    if form["type"] == "monitoring" and detail.get("parent") != parent_id:
        return (f"its parent is form {detail.get('parent')}, the plan "
                f"expects {parent_id}")
    have = {q["name"] for g in detail["question_group"]
            for q in g["question"]}
    want = {q["name"] for q in plan_questions(form)}
    if have != want:
        return (f"questions differ (missing {sorted(want - have)}, "
                f"extra {sorted(have - want)})")
    return None


def cmd_seed_forms(ctx):
    ensure_login(ctx)
    problems = [p for f in ctx.plan["forms"] for p in form_problems(f)]
    if problems:
        sys.exit("fix the plan first:\n  " + "\n  ".join(problems))
    forms = ctx.state.setdefault("forms", {})
    ordered = sorted(ctx.plan["forms"],
                     key=lambda f: f["type"] == "monitoring")
    for form in ordered:
        key = form["key"]
        parent_id = None
        if form["type"] == "monitoring":
            parent_id = forms.get(form["parent"], {}).get("id")
            if not parent_id and not ctx.args.dry_run:
                sys.exit(f"{key}: parent '{form['parent']}' not seeded")
        body = form_payload(form, parent_id)
        existing = existing_form(ctx, key, form)
        if existing:
            fid = existing["id"]
            why = form_mismatch(form, existing, parent_id)
            if why:
                sys.exit(f"{key}: form {fid} '{existing['name']}' already "
                         f"exists but does not match the plan: {why}. "
                         f"Rename the form in the plan, or delete it in the "
                         f"UI to rebuild.")
            forms[key] = {"id": fid}
            ctx.save()
            if existing.get("status") == "published":
                print(f"= {key}: exists as published form {fid}, skipped")
                continue
            # a draft left by a run that stopped before publishing
            print(f"~ {key}: form {fid} is a draft, publishing")
            if ctx.args.dry_run:
                continue
            if apply_dependencies(form, existing):
                ctx.ok("PUT", f"manage/forms/{fid}", existing)
            ctx.ok("POST", f"manage/forms/{fid}/publish")
            continue
        nq = len(plan_questions(form))
        if ctx.args.dry_run:
            print(f"+ {key}: '{form['name']}' ({form['type']}, {nq} questions)")
            continue
        editor = ctx.ok("POST", "manage/forms", body)
        fid = editor["id"]
        if apply_dependencies(form, editor):
            editor = ctx.ok("PUT", f"manage/forms/{fid}", editor)
        ctx.ok("POST", f"manage/forms/{fid}/publish")
        forms[key] = {"id": fid}
        ctx.save()
        print(f"+ {key}: form {fid} '{form['name']}' published "
              f"({nq} questions)")


def question_index(ctx, form_key):
    fid = ctx.state["forms"][form_key]["id"]
    detail = ctx.ok("GET", f"manage/forms/{fid}")
    return fid, {q["name"]: q for g in detail["question_group"]
                 for q in g["question"]}


# ---------------------------------------------------------------- load data

def row_key(row, cols):
    if not cols or any(blank(row[c]) for c in cols):
        return None  # a missing key cannot tell this row apart
    return "|".join(norm(row[c]) for c in cols)


def to_number(v):
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip().replace(",", "")
    s = re.sub(r"^[^\d\-.]+|[^\d.]+$", "", s)
    f = float(s)
    return int(f) if f.is_integer() else f


def to_date(v, fmt=None):
    """ISO date string. Refuses 03/04/2026-style text without a format."""
    from datetime import datetime
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if fmt:
        return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$", s)
    if m:
        return datetime(*map(int, m.groups())).strftime("%Y-%m-%d")
    if re.match(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$", s):
        raise ValueError(f"'{s}' could be day/month or month/day: set "
                         f"date_format in the data spec (e.g. %d/%m/%Y)")
    import pandas as pd
    return pd.to_datetime(s, errors="raise").strftime("%Y-%m-%d")


def to_geo(v):
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(v))
    if len(nums) < 2:
        raise ValueError("expected 'lat, lng'")
    lat, lng = float(nums[0]), float(nums[1])
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("out of range")
    return [lat, lng]


def match_option(q, raw, value_map):
    s = norm(lookup(value_map, raw))
    for o in q["options"]:
        if s.casefold() in (o.casefold(), option_value(o)):
            return option_value(o)
    raise ValueError(f"'{raw}' is not one of {q['options']}")


def mapped_blank(spec, qname, raw):
    """value_maps may send a raw value to "" meaning: no answer."""
    vm = spec.get("value_maps", {}).get(qname, {})
    hit = lookup(vm, raw)
    return hit is not raw and not norm(hit)


def convert(q, raw, spec):
    t = q["type"]
    vmap = spec.get("value_maps", {}).get(q["name"], {})
    if t == "number":
        return to_number(raw)
    if t == "date":
        return to_date(raw, spec.get("date_format"))
    if t == "geo":
        return to_geo(raw)
    if t == "option":
        return [match_option(q, raw, vmap)]
    if t == "multiple_option":
        sep = spec.get("multi_separator", r"[;,|/]")
        parts = [p for p in re.split(sep, str(raw)) if p.strip()]
        return sorted({match_option(q, p, vmap) for p in parts})
    return norm(raw)


class Loader:
    def __init__(self, ctx):
        self.ctx = ctx
        self.forms = {f["key"]: f for f in ctx.plan["forms"]}
        self.specs = {d["form"]: d for d in ctx.plan["data"]}
        self.admin = None
        self.parents = {}

    def admin_id(self, row, spec):
        adm = self.ctx.plan["administration"]
        aliases = adm.get("aliases", {})
        cols = spec.get("administration_columns") or []
        vals = [row[c] for c in cols]
        if any(blank(v) for v in vals):
            raise ValueError(f"administration columns {cols} incomplete")
        path = [norm(lookup(aliases, v)) for v in vals]
        if self.admin is None:
            if self.ctx.args.dry_run and not self.ctx.state.get("token"):
                return -1
            root, self.admin = fetch_admin_index(self.ctx)
            if root is None:
                if self.ctx.args.dry_run:
                    return -1
                raise ValueError("workspace not configured yet")
            self.admin[""] = root["id"]
        aid = self.admin.get(key_of(path))
        if aid is None:
            if self.ctx.args.dry_run:
                return -1
            raise ValueError(f"administration {' > '.join(path)} not seeded")
        return aid

    def registration_index(self, form_key):
        """key -> (uuid, admin_id, name) for a registration form's rows."""
        if form_key in self.parents:
            return self.parents[form_key]
        spec = self.specs[form_key]
        out = {}
        for _, row in read_table(self.ctx, spec).iterrows():
            k = row_key(row, spec["key_columns"])
            if k is None or k in out:
                continue  # the first row per key is the one loaded
            try:
                aid = self.admin_id(row, spec)
            except ValueError:
                continue
            out[k] = (self.uuid(form_key, k), aid,
                      self.dp_name(self.forms[form_key], row, spec, k))
        self.parents[form_key] = out
        return out

    def uuid(self, form_key, k):
        return str(uuidlib.uuid5(UUID_NS, f"{self.ctx.sub}/{form_key}/{k}"))

    def dp_name(self, form, row, spec, k):
        parts = []
        for q in plan_questions(form):
            col = spec["columns"].get(q["name"])
            if q.get("meta") and q["type"] not in ("geo", "administration") \
                    and col and not blank(row.get(col)):
                parts.append(norm(row[col]))
        return " - ".join(parts) or k

    def build(self, form, spec, row, qids):
        answers, errors = [], []
        is_mon = form["type"] == "monitoring"
        geo = None
        if is_mon:
            pk = row_key(row, spec["parent"]["key_columns"])
            parents = self.registration_index(spec["parent"]["form"])
            if pk not in parents:
                raise ValueError(f"no registration with key '{pk}'")
            puuid, aid, pname = parents[pk]
            k = row_key(row, spec["key_columns"])
            if k is None:
                raise ValueError(f"key columns {spec['key_columns']} blank")
            data = {"uuid": puuid, "administration": aid, "name": pname}
        else:
            k = row_key(row, spec["key_columns"])
            if k is None:
                raise ValueError(f"key columns {spec['key_columns']} blank")
            aid = self.admin_id(row, spec)
            data = {"uuid": self.uuid(form["key"], k), "administration": aid,
                    "name": self.dp_name(form, row, spec, k)}
        for q in plan_questions(form):
            qid = qids[q["name"]]["id"] if qids else q["name"]
            if q["type"] == "administration":
                if not is_mon:
                    answers.append({"question": qid, "value": aid})
                continue
            if q["type"] == "geo" and spec.get("geo"):
                g = spec["geo"]
                raw = f"{row.get(g['lat'])},{row.get(g['lng'])}" \
                    if "lat" in g else row.get(g["column"])
                if blank(row.get(g.get("lat", g.get("column")))):
                    raw = None
            else:
                col = spec["columns"].get(q["name"])
                if not col:
                    continue
                raw = row.get(col)
            if blank(raw) or mapped_blank(spec, q["name"], raw):
                if q.get("required"):
                    errors.append(f"{q['name']}: required but blank")
                continue
            try:
                v = convert(q, raw, spec)
            except (ValueError, TypeError, OverflowError) as e:
                errors.append(f"{q['name']}: {e}")
                continue
            if q["type"] == "geo":
                geo = v
            answers.append({"question": qid, "value": v})
        if geo and not is_mon:
            data["geo"] = geo
        data["submission_key"] = hashlib.sha256(
            f"{self.ctx.sub}/{form['key']}/{data['uuid']}/{k}".encode()
        ).hexdigest()[:64]
        return {"data": data, "answer": answers}, errors


def cmd_load_data(ctx):
    if not ctx.args.dry_run:
        ensure_login(ctx)
    loader = Loader(ctx)
    ordered = sorted(ctx.plan["data"],
                     key=lambda d: loader.forms[d["form"]]["type"]
                     == "monitoring")
    report_rows = []
    for spec in ordered:
        fk = spec["form"]
        if ctx.args.only and fk not in ctx.args.only:
            continue
        form = loader.forms[fk]
        fid, qids = (None, None)
        if not ctx.args.dry_run:
            fid, qids = question_index(ctx, fk)
        if not spec.get("key_columns"):
            sys.exit(f"{fk}: data needs key_columns (a stable id per record; "
                     f"for monitoring e.g. parent key + date) so every row "
                     f"gets its own record and re-runs do not duplicate rows")
        df = read_table(ctx, spec)
        sent = skipped = failed = 0
        samples = []
        for i, row in df.iterrows():
            line = i + 2 + spec.get("header_row", 0)
            try:
                payload, warns = loader.build(form, spec, row, qids)
            except ValueError as e:
                skipped += 1
                report_rows.append((fk, line, "skipped", str(e)))
                continue
            for w in warns:
                report_rows.append((fk, line, "warning", w))
            if not payload["answer"]:
                skipped += 1
                report_rows.append((fk, line, "skipped", "no answers"))
                continue
            if ctx.args.dry_run:
                if len(samples) < 2:
                    samples.append(payload)
                sent += 1
                continue
            status, p = ctx.request("POST", f"form-pending-data/{fid}",
                                    payload)
            if status == 200:
                sent += 1
            else:
                failed += 1
                report_rows.append((fk, line, "failed",
                                    f"{status} {json.dumps(p)[:300]}"))
            if (sent + failed) % 50 == 0:
                print(f"  {fk}: {sent + failed}/{len(df)}", flush=True)
        verb = "valid" if ctx.args.dry_run else \
            "accepted (re-sent rows are ignored by the server)"
        print(f"{fk}: {len(df)} rows, {sent} {verb}, {skipped} skipped, "
              f"{failed} failed")
        for s in samples[:1]:
            print("  sample payload (unit ids are -1 until the workspace "
                  "exists):", json.dumps(s))
    rpt = os.path.join(ctx.plan_dir, "load-report.csv")
    import csv
    with open(rpt, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["form", "source_row", "kind", "message"])
        w.writerows(report_rows)
    kinds = {}
    for r in report_rows:
        kinds[r[2]] = kinds.get(r[2], 0) + 1
    print(f"report: {rpt} {kinds or '(clean)'}")


# -------------------------------------------------------------------- status

def cmd_status(ctx):
    ensure_login(ctx)
    root, idx = fetch_admin_index(ctx)
    levels = ctx.ok("GET", "levels-management")
    print(f"workspace: {ctx.scheme}://{ctx.host()}")
    print(f"levels: {', '.join(lv['name'] for lv in levels)}")
    print(f"administrations: {len(idx)} (root '{root['name']}')")
    for key, f in (ctx.state.get("forms") or {}).items():
        s, p = ctx.request("GET", f"form-data/{f['id']}?page=1")
        total = p.get("total") if s == 200 and isinstance(p, dict) else s
        print(f"form {key} ({f['id']}): {total} datapoints")


def cmd_apply(ctx):
    for step in (cmd_login, cmd_configure, cmd_seed_admin, cmd_seed_forms,
                 cmd_load_data, cmd_status):
        print(f"== {step.__name__[4:].replace('_', '-')}")
        step(ctx)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--state", help="default: mis-state.json beside the plan")
    ap.add_argument("--connect", help="send requests to this URL with the "
                    "workspace Host header (local/docker testing)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "register", "resend-activation", "login",
                 "configure", "status", "apply"):
        sub.add_parser(name)
    a = sub.add_parser("activate")
    a.add_argument("token", help="activation token or the full link")
    for name in ("seed-admin", "seed-forms", "load-data"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true")
        if name == "load-data":
            p.add_argument("--only", nargs="*", help="form keys")
    args = ap.parse_args()
    for flag in ("dry_run", "only"):
        if not hasattr(args, flag):
            setattr(args, flag, None if flag == "only" else False)
    ctx = Ctx(args)
    fn = {"check": cmd_check, "register": cmd_register,
          "resend-activation": cmd_resend, "activate": cmd_activate,
          "login": cmd_login, "configure": cmd_configure,
          "seed-admin": cmd_seed_admin, "seed-forms": cmd_seed_forms,
          "load-data": cmd_load_data, "status": cmd_status,
          "apply": cmd_apply}[args.cmd]
    try:
        fn(ctx)
    except ApiError as e:
        sys.exit(f"API error: {e}")
    finally:
        if not args.dry_run and set(ctx.state) - {"subdomain"}:
            ctx.save()


if __name__ == "__main__":
    main()
