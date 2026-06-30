# Design: Remove `window.forms` → Runtime Forms Fetch

**Status:** Design (ready for `/sc:implement`)
**Scope:** `window.forms` only. `window.levels` / `window.topojson` / `window.appConfig` / `window.roleFeatures` stay baked.
**Related:** [iwsims-dashboard-config-example.md](./iwsims-dashboard-config-example.md), `generate_config.py`, `v1_forms/tasks.py`, `v1_forms/signals.py`

---

## 1. Problem & Root Cause

Published forms do not reflect in the web app without a config rebuild + hard reload.

Forms are baked into a **load-once global script**. `public/index.html` loads `config.js` → `get_config_file` serves `config.min.js`, which sets `var forms = [...]` as a `window.forms` global. Two staleness layers:

1. **Load order** — the SPA reads `window.forms` once at startup; forms published after page load never appear in the open tab.
2. **No cache-busting** — `get_config_file` sets no `Cache-Control`/`ETag`; the browser heuristically caches `config.js`, so even a reload can serve the stale bundle.

Backend regeneration is **not** broken: the worker-regenerated `config.min.js` already contains the published form. This is purely a delivery-model problem.

---

## 2. Target Architecture

Forms move from a baked global to a runtime fetch into the existing pullstate store.

```
BEFORE                                  AFTER
──────                                  ─────
index.html <script config.js>           index.html <script config.js>
  └─ var forms = [...]  (baked)            └─ (no var forms)
        │                                 App bootstrap (blocks render)
   window.forms                             └─ GET /api/v1/forms/published
        │                                          │
   store.forms = window.forms.sort()         store.allForms = data
        │                                     store.forms = filtered+sorted
   consumers read window.forms            consumers read store.allForms / accessor
```

`allForms` = full published list (replaces `window.forms`). `forms` = assignment-filtered, sorted UI render list (unchanged semantics).

### Bootstrap data flow

```
App mount  (loading = true, render blocked — Decision Q2)
  │
  ├─ GET /forms/published ──► [{id,name,version,content}]
  │        store.update(s => s.allForms = data)
  │
  ├─ if AUTH_TOKEN: GET /profile ──► reloadData(profile)
  │        store.forms = filterByAssignment(profile, s.allForms).sort()
  │
  └─ all resolved → setLoading(false) → render
```

---

## 3. Backend Design

### 3.1 New endpoint — `GET /api/v1/forms/published`

| Property | Value |
|---|---|
| Path | `^(?P<version>(v1))/forms/published$` in `api/v1/v1_forms/urls.py` |
| View | `list_published_forms` in `api/v1/v1_forms/views.py` |
| Method | `GET` |
| Auth | **`AllowAny`** — parity with public `config.js`; dashboards in `config.allowedGlobal` render pre-login (Decision Q1). |
| Cache-Control | `no-cache` response header (kills the browser-cache staleness layer). |

**Response** (array, shape-identical to the old baked `var forms`):

```json
[
  { "id": 1782832048404, "name": "New Form", "version": 1,
    "content": { /* FormDataSerializer(instance=form).data */ } }
]
```

**Selection mirrors `generate_config.py` exactly** — `Forms.objects.filter(status=FormStatus.published)` with **no** `parent__isnull` filter (parents **and** children, so dashboard helpers that resolve child forms by id keep working). This differs from the existing `list_form` (`/forms`), which filters `parent__isnull=True` — do not reuse it.

**View (interface — build in `/sc:implement`):**

```python
@extend_schema(tags=["Form"], summary="Published forms with content")
@api_view(["GET"])
@permission_classes([AllowAny])
def list_published_forms(request, version):
    payload = get_published_forms_payload()      # §3.2, cached
    resp = Response(payload, status=status.HTTP_200_OK)
    resp["Cache-Control"] = "no-cache"
    return resp
```

### 3.2 Shared serializer helper (DRY with generate_config) + server-side cache

Extract the forms loop duplicated between `generate_config.py` and the new view into one cached function. **Use the existing `get_cache`/`create_cache` helpers** (`v1_data/functions.py`) so the payload participates in the established invalidation path (Decision Q4, aligned with Q3 — see §3.4):

```python
# api/v1/v1_forms/functions.py
from api.v1.v1_data.functions import get_cache, create_cache

PUBLISHED_FORMS_CACHE = "published-forms"

def get_published_forms_payload():
    cached = get_cache(PUBLISHED_FORMS_CACHE)
    if cached is not None:
        return cached
    payload = [
        {"id": f.id, "name": f.name, "version": f.version,
         "content": FormDataSerializer(instance=f).data}
        for f in Forms.objects.filter(status=FormStatus.published).all()
    ]
    create_cache(PUBLISHED_FORMS_CACHE, payload)
    return payload
```

- `get_cache`/`create_cache` are date-prefixed and **bypass under `TEST_ENV`** — no per-request re-serialization in prod, correct freshness in tests.
- No version-embedded key needed: invalidation is handled blanket-style in §3.4.

### 3.3 `generate_config.py` changes

- Remove the `forms = []` loop and the `"var forms=", json.dumps(forms), ";"` segment + `del forms`.
- Keep `levels`, `topojson`, `appConfig`, `roleFeatures` untouched.
- Net: `config.min.js` no longer carries form definitions (smaller bundle).

### 3.4 Cache invalidation — why Q4 aligns with Q3

Already in place: [`v1_forms/signals.py`](../../backend/api/v1/v1_forms/signals.py) connects `post_save`/`post_delete` on `Forms`/`QuestionGroup`/`Questions`/`QuestionOptions` → **`cache.clear()`** (wipes the entire default cache). `refresh_form_config` also calls `clear_cache` on publish.

Therefore the new `published-forms` cache entry is invalidated automatically by **both**:
1. the form-mutation signal (`cache.clear()`), and
2. the kept `clear_cache` call (Decision Q3).

**`refresh_form_config` change:** keep `clear_cache`; **drop `generate_config`** from the publish path (forms are now fetched live; only caches need eviction). `clear_cache` remains necessary to evict the `published-forms` payload **and** the per-form `webform-{id}-…` cache.

> Q4 ↔ Q3 confirmed: the server-side cache is safe *because* `clear_cache` (and the signal's `cache.clear()`) is retained on publish. Removing `clear_cache` would strand a stale `published-forms` payload until the date-prefix rolls over at midnight.

---

## 4. Frontend Design

### 4.1 Store (`src/lib/store.js`)

```diff
- forms: window.forms.sort(sortArray),
+ allForms: [],   // full published list from /forms/published
+ forms: [],      // assignment-filtered + sorted (UI render list)
  levels: window.levels,
```

`forms` init `[]` removes the `window.forms.sort()` crash risk.

### 4.2 Fetch + bootstrap (`src/util/form.js`, `src/App.js`)

- `fetchPublishedForms()` in `util/form.js`: `GET forms/published` → `store.update(s => { s.allForms = data })`.
- `reloadData(profile, dataset)` sources the full list from `s.allForms` (not `window.forms`):

```js
const filterFormByAssigment = (profile = {}, allForms = []) => {
  if (!Object.keys(profile).length) { return allForms; }
  return profile.forms.length
    ? allForms.filter((x) => profile.forms.map((f) => f.id).includes(x.id))
    : allForms;
};
```

- **Render blocked until forms load (Decision Q2):** `App.js` keeps `loading = true` until `fetchPublishedForms()` resolves (and `/profile` when a token exists). Run the forms fetch on mount for **all** routes (public + authed) so public dashboards get `allForms` too. `reloadData` runs after both resolve.
- `LoginForm` / `RegistrationForm` already call `reloadData(res.data)`; `allForms` is already populated from the mount fetch, so they just re-filter.

### 4.3 Consumer migration (`window.forms` → store/accessor)

One snapshot accessor for non-component code:

```js
// util/form.js
export const getForms = () => store.getRawState().allForms || [];
```

| File | Current | Change |
|---|---|---|
| `util/form.js` | `window.forms` ×3 | `allForms` param / `getForms()` |
| `lib/store.js` | `window.forms.sort` | `[]` init |
| `dashboard/EscalationTable.jsx` | `window.forms?.flatMap` | `store.useState(s=>s.allForms)` |
| `dashboard/DashboardMap/getQuestionOptions.js` | `window.forms` | `getForms()` |
| `dashboard/DashboardFilters.jsx` | `window.forms` ×2 | `getForms()` / store |
| `dashboard/.../individual-overview/shared/helpers.js` | `window.forms` ×2 | `getForms()` |
| `components/filters/FormDropdown.js` | `window.forms` ×3 | `store.useState(s=>s.allForms)` |
| `components/filters/DataFilters.js` | `window.forms` | `store.useState` / `getForms()` |
| `*/__test__/*` | set/delete `window.forms` | seed store via `store.update` / mock `getForms` |

> React render paths prefer `store.useState(s => s.allForms)` (reactive); pure helpers use the `getForms()` snapshot.

---

## 5. Sequence — publish reflects without rebuild

```
Editor publishes form
  ├─ Forms.status = published; version bump
  ├─ post_save signal → cache.clear()           [evicts published-forms + webform caches]
  └─ refresh_form_config (async): clear_cache    [Decision Q3 — generate_config dropped]
Any user loads/reloads app
  └─ GET /forms/published (Cache-Control: no-cache, server cache MISS → fresh)
        └─ new form present ✔  (no config.min.js rebuild)
```

---

## 6. Acceptance Criteria

- Publish a form → reload app (no `generate_config` rerun) → appears in `s.allForms`, dashboards, `FormDropdown`.
- Unpublish → reload → disappears.
- No `window.forms` reference remains in `frontend/src` (excluding removed test scaffolding).
- `generate_config` output contains no `var forms=`.
- `/forms/published` returns parents **and** children with full `content` (parity with old baked list); `Cache-Control: no-cache`; `AllowAny`.
- App render is gated until forms load (no flash of empty dropdowns).
- After publish, `cache.clear()`/`clear_cache` evicts the `published-forms` payload (next fetch is fresh).

---

## 7. Decisions (locked)

1. **Auth** — `AllowAny`, public like `config.js`.
2. **Bootstrap** — block initial render until forms load.
3. **`refresh_form_config`** — keep `clear_cache`; drop `generate_config` from publish path.
4. **Server-side cache** — yes, via shared `get_cache`/`create_cache`; invalidated by the retained `clear_cache`/signal `cache.clear()` (aligned with #3).

---

## 8. Out of Scope

- `window.levels`, `window.topojson`, `window.appConfig`, `window.roleFeatures` (stay baked).
- Mobile app (separate SQLite/config path).
- Live push to open tabs (websocket/poll) — deferred.

**Next:** `/sc:implement` — backend (helper extraction + cached endpoint + `generate_config`/`refresh_form_config` edits, independently testable), then frontend store/bootstrap gating, then consumer migration + tests.
