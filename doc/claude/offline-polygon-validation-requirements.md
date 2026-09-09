# Offline Polygon Validation (Mobile) — Requirements

**Status**: Requirements only. No architecture, no schema design, no code.
**Next**: `/sc:design` for architecture, then `/sc:workflow` for implementation planning.
**Sources**:
- Validation rules — `akvo/african-bamboo-odk-external-validations` → `docs/{polygon-validation, plot-overlap-detection, basic-polygon-overlap-validation, polygon-validation-implementation-plan}.md`
- Capture UX, value format, config contract — `akvo/akvo-react-form` **#192** (`TypeGeoDrawing`), commit `e7d786d`

---

## 1. Context and Why This Is Not a Straight Port

The reference validator is a **separate Android app** launched by ODK Collect over an intent. It owns its
own Room database, must persist "plots" itself, and blocks the form by returning
`RESULT_OK, value=null` to clear the field.

Akvo MIS collects data **inside** the app. That changes three things:

| Reference validator mechanism | Akvo MIS equivalent | Consequence |
|---|---|---|
| Intent extras (`shape`, `plot_name`, `region`) | Question answers already in `FormState.currentValues` | No intent contract, no XLSForm appearance changes |
| `RESULT_OK value=null` to clear the field | `FormState.feedback[questionId]` + submit gate in [FormNavigation.js:164](../../app/src/form/support/FormNavigation.js#L164) | Blocking already exists; reuse it |
| `plots` table + `isDraft` + `instanceName` matching to submissions | `datapoints` table already holds local **and** synced records offline | The entire draft-lifecycle chapter of the source plan is dead weight here |

**The draft/sync-matching machinery in the source docs must not be ported.** It exists only
because the reference validator cannot see Kobo's submissions. Akvo MIS already syncs datapoints per form
to local SQLite, so both "downloaded data" (Scenario 1) and "unsubmitted local data"
(Scenario 2) are one query against one table.

---

## 2. Current-State Findings

Established by inspection, not assumption:

| Finding | Evidence |
|---|---|
| Backend already defines `geoshape`=14, `geotrace`=15 with a `center` field | [constants.py:14](../../backend/api/v1/v1_forms/constants.py#L14), [serializers.py:149](../../backend/api/v1/v1_forms/serializers.py#L149) |
| Mobile form endpoint uses the **same** `WebFormDetailSerializer` as web | [v1_mobile/views.py:146](../../backend/api/v1/v1_mobile/views.py#L146) |
| ⚠️ A `geoshape` question therefore **already reaches the app** and renders as a **plain text input** via the `default:` branch | [QuestionField.js:157](../../app/src/form/components/QuestionField.js#L157) |
| App has no polygon field — only single-point `geo` | [TypeGeo.js](../../app/src/form/fields/TypeGeo.js), [fields/index.js](../../app/src/form/fields/index.js) |
| `QUESTION_TYPES` has no `geoshape`/`geotrace` | [constants.js:26](../../app/src/lib/constants.js#L26) |
| No map library, no geometry library in dependencies | [package.json](../../app/package.json) |
| `react-native-webview` **is** already a dependency (13.13.5) | [package.json:64](../../app/package.json#L64) |
| Field validation is already `async` and awaited — a DB-backed check can slot in | [FormNavigation.js:112](../../app/src/form/support/FormNavigation.js#L112) |
| Navigation between groups is deliberately **not** blocked; **submit** is blocked by `validateAllGroups()` | [FormNavigation.js:135](../../app/src/form/support/FormNavigation.js#L135), [:164](../../app/src/form/support/FormNavigation.js#L164) |
| Datapoint answers live in `datapoints.json` as `{questionId: answer}` | [crud-datapoints.js:10](../../app/src/database/crud/crud-datapoints.js#L10) |
| `datapoints.geo` is `VARCHAR(255)` — a point, not a polygon | [tables.js:53](../../app/src/database/tables.js#L53) |
| GPS tuning knobs already live in `config` and sync from backend | [tables.js:23-25](../../app/src/database/tables.js#L23) |
| `Questions.extra` is a free-form `JSONField` already serialized to mobile — **no model change needed for per-question geo config** | [models.py:148](../../backend/api/v1/v1_forms/models.py#L148), [serializers.py](../../backend/api/v1/v1_forms/serializers.py) `get_extra` |
| **Web already collects polygons end to end.** `akvo-react-form-editor@2.0.4` offers `geotrace`/`geoshape` as authorable types with a `SettingGeo` panel; [Forms.jsx:532](../../frontend/src/pages/forms/Forms.jsx#L532) passes form JSON straight to ARF `<Webform>`, and ARF **2.7.9** switches on the type internally | [frontend/package.json:11-12](../../frontend/package.json#L11), `node_modules/akvo-react-form-editor/dist` |
| Frontend `QUESTION_TYPES` is referenced **only** by `EditableCell` / `ReadOnlyCell` / `RawDataTable` — it drives **data display**, not form rendering | [frontend/src/lib/constants.js:14](../../frontend/src/lib/constants.js#L14) |
| `@turf/turf ^6.5.0` is already a declared frontend dependency — pure JS, so it runs in React Native too | [frontend/package.json:9](../../frontend/package.json#L9) |
| No `Forms` field gates web vs mobile; client targeting is by `MobileAssignment` and by which questions a form author adds | [v1_forms/models.py:18](../../backend/api/v1/v1_forms/models.py#L18) |

### 2.1 What akvo-react-form #192 already settles

`TypeGeoDrawing` shipped in ARF v2.7.8 (commit `e7d786d`). It defines the capture half of this
feature, so that half is a **port, not a design exercise**:

| Contract | Value | Evidence |
|---|---|---|
| Answer format | `[[lat, lng], [lat, lng], ...]` — array of numeric pairs, same family as `TypeGeo`'s `[lat, lng]` | `akvo-react-form` `src/fields/TypeGeoDrawing.jsx:170` |
| Types | `geotrace` (open, `Polyline`) and `geoshape` (closed, `Polygon`) share one format; only rendering and the min-point rule differ | `GeoGeometry.jsx:25` |
| Min points | geotrace ≥2, geoshape ≥3 | `TypeGeoDrawing.jsx:352-357` |
| Per-question config | `extra.geoConfig.accuracyThreshold` — when set, the accuracy control is replaced by a read-only "Xm (configured)" label | `TypeGeoDrawing.jsx:98` |
| Capture modes | `tap` (tap map to add), `manual` (drag marker → Record), `auto` (`watchPosition` + 10 s interval, points below the accuracy threshold discarded) | `TypeGeoDrawing.jsx:168-334` |
| Map stack | **Leaflet** | `package.json` — `leaflet`, `react-leaflet` |
| i18n | ~40 `geoDrawing*` keys already named and translated (en/id/in/fr/de) | `src/locale/*.json` |
| Component split | 5 sub-components extracted to `src/support/` to keep the field under ~300 lines | commit message `e7d786d` |

**ARF does not implement any of the reference validator's validation.** It has no area check, no
self-intersection check, and no overlap detection — only the min-point rule. The two sources
are complementary, not overlapping: **ARF #192 → FR-1 (capture); the reference validator → FR-2/FR-3
(validation).**

**Implication**: this is two features stacked — *polygon capture* and *overlap validation*.
The reference validator's docs assume capture already exists (ODK Collect draws the geoshape); it does
not exist in `app/`. ARF #192 supplies it for web, and that is what gets ported.

---

## 3. Confirmed Decisions

| # | Decision | Chosen |
|---|---|---|
| D1 | Scope | **Validation + map review screen.** No offline satellite tile packs. |
| D2 | Overlap candidates | **Same form, all local datapoints** — both `locallyCreated=1` (unsubmitted) and synced. |
| D3 | Overlap threshold | **Configurable, default 20%.** Resolves the 5% / 20% conflict between source docs in favour of the documented GPS-drift rationale, with a knob for field conditions. |
| D4 | Map rendering | **WebView + Leaflet.** Reuses the installed `react-native-webview`; no new native module, no EAS dev-client rebuild. |
| D5 | Capture implementation | **Port ARF `TypeGeoDrawing` (#192)** and its `src/support/` decomposition into `app/src/form/support/`, preserving the value format, `extra.geoConfig` contract, capture modes, and `geoDrawing*` i18n keys. |
| D6 | Overlap scope *(Q2)* | **`geoshape` only.** `geotrace` is captured and stored but never area-checked, self-intersection-checked, or overlap-checked. |
| D7 | Validation trigger *(Q4)* | **Explicit "Validate now" button** on the polygon field. Validation never runs implicitly on blur, on Next, or on every submit pass. |
| D8 | Background auto-record *(Q3b)* | **Yes — auto-record continues when backgrounded**, via a foreground service with a persistent notification. Requires a development build (§3.2). |
| D9 | Repeatable groups *(Q6)* | **Supported.** Polygons may appear in repeatable groups. Polygons **within the same datapoint are never checked against each other** — only against other datapoints. |
| D10 | Monitoring forms *(Q7)* | **No polygon prefill.** A monitoring form never inherits its parent's polygon, so the parent-overlap problem does not arise. |
| D11 | Deleted / rejected datapoints *(Q8)* | **No exclusion logic.** The app has no datapoint-deletion trigger, so every stored datapoint is a valid overlap candidate. |
| D12 | ARF sync *(Q10)* | **Track ARF upstream by default**, but every re-port is gated on React Native compatibility review. The `[[lat,lng],…]` value format is the contract that must not diverge. |
| D13 | `geoConfig` authoring *(Q5)* | **A form-builder UI is required** — hand-edited JSON is not acceptable. Preferred home is an extension to `SettingGeo.jsx` in **`akvo-react-form-editor`** (upstream repo), not akvo-mis frontend. See FR-5.7.1. |

**D4 is reinforced by D5**: ARF already renders geometry with Leaflet. The WebView page can
carry over the same `GeoGeometry` / `RecordedMarkers` / `FitBounds` / `MapClickHandler` logic
almost verbatim rather than being invented for React Native — one map implementation, two hosts.

D4 accepted trade-off: satellite basemap tiles require connectivity. Offline, polygons render
on a blank canvas. Scenario 1 and 2 say "overlaid on a high resolution satellite view" — **this
is knowingly not met offline** (see Open Question Q1).

### 3.1 Component mapping — ARF `src/support/` → `app/src/form/support/`

Which pieces survive as React Native components and which collapse into the WebView page:

| ARF component | Lines | Disposition in `app/` |
|---|---|---|
| `TypeGeoDrawing.jsx` | 503 | → `app/src/form/fields/TypeGeoDrawing.js` — the field; hosts the WebView and the RN controls |
| `CoordinatePreview.jsx` | 63 | → `app/src/form/support/CoordinatePreview.js` — pure text, straight RN port |
| `GeoDrawingControls.jsx` | 325 | → `app/src/form/support/GeoDrawingControls.js` — RNEUI buttons; likely splits further to respect the 200–400 line guideline |
| `GeoGeometry.jsx` | 55 | → **into the WebView Leaflet page** (`Polyline`/`Polygon` are Leaflet, not RN) |
| `RecordedMarkers.jsx` | 81 | → **into the WebView Leaflet page** |
| `GeoDrawingMapHandlers.jsx` | 106 | → **into the WebView Leaflet page** (`FitBounds`, `MapClickHandler`, marker icons) |

Web geolocation APIs have direct Expo equivalents, so the capture logic ports rather than
being redesigned:

| ARF (web) | `app/` equivalent |
|---|---|
| `navigator.geolocation.getCurrentPosition` | `loc.getCurrentLocation` — already wrapped in [`app/src/lib`](../../app/src/lib) and used by `TypeGeo` |
| `navigator.geolocation.watchPosition` | `expo-location` `watchPositionAsync` |
| `antd` `Modal.confirm` / `Modal.error` | RN `Alert` / existing dialog components |
| `form.setFieldsValue({ [id]: … })` | `FormState.update((s) => { s.currentValues = … })` |
| `uiText` prop | existing `i18n.text(activeLang)` layer |

**New requirement created by the split**: the RN side and the WebView side must exchange
coordinates over `postMessage`. Tap-to-add and marker drag originate inside the WebView;
GPS-recorded points originate in RN. Both must converge on one ordered point list.

### 3.2 Build-mode consequence of D8 — Expo Go is ruled out

Verified against the current app:

| Question asked | Answer |
|---|---|
| Does the Expo SDK need upgrading? | **No.** SDK 53 + `expo-location ~18.1.6` already support background location. |
| Can Expo Go run background auto-record? | **No.** Background location needs `ACCESS_BACKGROUND_LOCATION` and `FOREGROUND_SERVICE_LOCATION` compiled into the native binary. Expo Go ships a fixed binary without them. |
| Is a development build already in place? | **No.** `expo-dev-client` is not a dependency, and the `development` profile in [eas.json](../../app/eas.json) has no `"developmentClient": true` — it builds a plain APK. |
| Is `expo-location` configured natively? | **No.** It has no config-plugin entry in [app.json:36](../../app/app.json#L36), and [loc.js:4](../../app/src/lib/loc.js#L4) requests **foreground permission only**. |

**What D8 therefore requires** (all app-side, no SDK bump):

1. Add `expo-dev-client`; set `"developmentClient": true` on the `development` EAS profile.
2. Add the `expo-location` config plugin to `app.json` with background location enabled and
   the permission strings.
3. Register a `TaskManager` background location task and start it with
   `Location.startLocationUpdatesAsync({ foregroundService: {...} })`.
4. Extend [loc.js](../../app/src/lib/loc.js) with `requestBackgroundPermissionsAsync` —
   a **second, separately-granted** Android permission that users can refuse independently
   of foreground.
5. `./dc-mobile.sh` keeps working: the container still runs the Metro bundler
   (`expo start --port 19000`); only the client on the handset changes from Expo Go to an
   installed dev-client APK.

**Consequence for reviewers**: the "no new native module, no dev-client rebuild" argument that
supported D4 is **partly spent** — D8 already forces a dev client. D4 still stands, because
Leaflet-in-WebView avoids a native map SDK, its token, and its licensing terms. But this is the
premise to re-examine if D4 is ever revisited (§11).

---

## 4. Functional Requirements

### FR-1 — Polygon capture field *(ported from ARF #192)*

- **FR-1.1** The app renders a dedicated field for `geoshape` (closed ring) and `geotrace`
  (open path) question types instead of falling through to a text input.
- **FR-1.2** The answer value is an ordered array of `[lat, lng]` numeric pairs, **identical
  to ARF's format**, so a datapoint collected on mobile and one collected on web are
  indistinguishable to the backend.
- **FR-1.3** Three capture modes, matching ARF:
  - **FR-1.3a Tap** — tap the map to append a point.
  - **FR-1.3b Manual** — drag a marker to a position, press Record to append it.
  - **FR-1.3c Auto-record** — a GPS watch appends the current position on a fixed interval
    (10 s in ARF) while the enumerator walks the boundary.
- **FR-1.4** In auto-record, a fix whose accuracy is worse than the configured threshold is
  **discarded, not appended** (ARF `TypeGeoDrawing.jsx:318`).
- **FR-1.5** The accuracy threshold comes from `extra.geoConfig.accuracyThreshold` when the
  form defines it, and is then read-only. Otherwise the enumerator may adjust it, defaulting
  to 15 m (ARF FR-AUTO-17/18).
- **FR-1.6** During auto-record the live GPS position is shown distinctly from recorded
  points, along with its current accuracy.
- **FR-1.7** Recorded points are individually visible; the enumerator can remove a single
  point, undo the last point, or clear all — clearing more than 3 points asks for confirmation.
- **FR-1.8** Live feedback: point count, type label (route/polygon), and — for `geoshape`
  with ≥3 points — the enclosed area. *(Area display is an Akvo MIS addition; ARF has no
  area calculation.)*
- **FR-1.9** The map viewport auto-fits recorded points, except while auto-recording, when it
  follows the live position.
- **FR-1.10** A "Get my location" action recentres the map without appending a point.
- **FR-1.11** For `geoshape`, the ring closes implicitly; the enumerator never re-captures the
  first point to close it.
- **FR-1.12** The value round-trips through `datapoints.json` and through form save/resume
  without loss of precision, and survives leaving and re-entering the question group.
- **FR-1.13** The value is compatible with the XLSForm export
  ([xlsform_export.py:102](../../backend/api/v1/v1_forms/services/xlsform_export.py#L102)).
- **FR-1.14** GPS watches and intervals are torn down on unmount, on leaving the question
  group, and when the app is backgrounded — no orphaned location subscription (NFR-5).
- **FR-1.15** All strings reuse ARF's `geoDrawing*` key names through the app's `i18n` layer,
  so translations transfer rather than being re-authored.

#### FR-1.16 — Touchpoint checklist (mobile)

Registering the type is **necessary but not sufficient**. Adding the key to `QUESTION_TYPES`
alone produces a field that renders but validates wrongly. All seven must land together:

| # | File | Change | Symptom if skipped |
|---|---|---|---|
| 1 | [app/src/lib/constants.js:26](../../app/src/lib/constants.js#L26) | Add `geoshape`, `geotrace` to `QUESTION_TYPES` | Type never matches anywhere |
| 2 | [QuestionField.js:157](../../app/src/form/components/QuestionField.js#L157) | Add `case` → `<TypeGeoDrawing>` | Falls to `default:` → renders a **plain text input** |
| 3 | `app/src/form/fields/TypeGeoDrawing.js` + [fields/index.js](../../app/src/form/fields/index.js) | New component + export | Nothing to render |
| 4 | [form/lib/index.js:364](../../app/src/form/lib/index.js#L364) | Add `case` → `Yup.array()`, mirroring `'geo'` | Falls to `default: Yup.string()` → **an array fails a string schema**; silent wrong validation |
| 5 | [form/lib/index.js:406](../../app/src/form/lib/index.js#L406) | Exclude polygon types from datapoint-name generation, as `geo` already is | Raw coordinate arrays leak into the datapoint name |
| 6 | [form/lib/index.js:462](../../app/src/form/lib/index.js#L462) | Add the `geo`-style `'' → []` branch in `transformValue` | Empty polygon becomes `''` instead of `[]`; breaks resume and prefill |
| 7 | [FormNavigation.js:56](../../app/src/form/support/FormNavigation.js#L56), [:102](../../app/src/form/support/FormNavigation.js#L102) | Add polygon types to the `['cascade','multiple_option','option','geo']` defaultVal list | Unanswered polygon defaults to `''` not `null` → **wrong required-check behaviour** |

Items 4 and 7 are the quiet failures: the field looks correct on screen and validates wrongly.

#### FR-1.17 — Web display parity *(optional, separate from capture)*

Web **capture** needs no change (§2). But `frontend/src/lib/constants.js` `QUESTION_TYPES` drives
manage-data display, so a polygon answer currently renders as a raw coordinate array in
`EditableCell` / `ReadOnlyCell` / `RawDataTable`. Adding the types there is a **display fix**,
not an enabler, and is independent of this mobile work.

### FR-2 — Single-polygon validation

Runs before any overlap check. Ported directly from `polygon-validation.md`.

| Check | Rule | Message |
|---|---|---|
| FR-2.1 Format | Value parses as a polygon | "Invalid polygon format. Unable to parse the shape data." |
| FR-2.2 Vertices | ≥3 distinct points | "Polygon has too few vertices. A valid shape requires at least 3 points." |
| FR-2.3 Area | > 10 m² — **fixed constant** (FR-5.B) | "Polygon area is too small. Minimum required: 10 square meters." |
| FR-2.4 Self-intersection | No edge crosses another edge | "Polygon lines intersect or cross each other. Please redraw the shape." |

- **FR-2.5** Messages are translatable through the existing `i18n` layer, not hardcoded English.
- **FR-2.6** *(D6)* **`geoshape` only.** `geotrace` questions are captured, stored, and synced
  normally but are exempt from FR-2.3, FR-2.4 and all of FR-3. Only the min-point rule
  (FR-1) applies to them.

### FR-3 — Offline overlap detection

- **FR-3.1** A new polygon is checked against every datapoint of the **same form** already on
  the device, regardless of `submitted`, `syncedAt`, or `locallyCreated`.
- **FR-3.2** The datapoint currently being edited is excluded from its own check.
- **FR-3.3** Administration/region is **not** used as a filter. Ported verbatim from
  `plot-overlap-detection.md`: filtering by region produces false negatives on boundary plots,
  on mis-selected regions, and defeats fraud detection.
- **FR-3.4** A bounding-box pre-filter narrows candidates before any precise geometry maths.
- **FR-3.5** Overlap ratio = `intersection_area / min(new_area, existing_area)`.
- **FR-3.6** Ratio ≥ threshold (default 0.20) → validation fails.
- **FR-3.7** The check runs entirely offline. No network call, no server round-trip, no sync
  required between collecting two overlapping plots on the same device.
- **FR-3.8** Multiple simultaneous overlaps are all detected and all reported, not just the first.
- **FR-3.9** *(D6)* Overlap detection applies to `geoshape` questions only.
- **FR-3.10** *(D9)* Polygons captured in a **repeatable group** are each checked against other
  datapoints, but **never against each other within the same datapoint**. Two repeat instances
  of the same submission may overlap freely.
- **FR-3.11** *(D9)* An overlap error in a repeatable group identifies **which repeat instance**
  failed, not just the question.
- **FR-3.12** *(D10)* Monitoring forms do **not** prefill the parent's polygon, so a monitoring
  submission is never compared against its own parent's boundary.
- **FR-3.13** *(D11)* No datapoint is excluded on approval status or deletion state — the app
  has no deletion trigger, so all stored datapoints are candidates.

### FR-4 — Error reporting and blocking

- **FR-4.1** Overlap failure message follows the source format, using the datapoint name that
  `generateDataPointName` already produces from `meta: true` questions:
  ```
  New plot for <current datapoint name> overlaps with plot for <existing datapoint name>
  ```
- **FR-4.2** With multiple overlaps, every conflicting datapoint name is listed.
- **FR-4.3** A failing polygon surfaces through the existing `FormState.feedback` channel and
  renders in the existing `err-validation-text` slot ([QuestionField.js:182](../../app/src/form/components/QuestionField.js#L182)).
- **FR-4.4** Consistent with current app behaviour, a failure does **not** block moving between
  question groups. It **does** block submission via `validateAllGroups()`.
- **FR-4.5** The enumerator can edit the polygon and re-run validation any number of times;
  re-validation replaces the previous result rather than accumulating errors.
- **FR-4.6** When the overlap is resolved, the error clears and submission proceeds (Scenario 3).

#### FR-4.7 — Explicit "Validate now" trigger *(D7)*

- **FR-4.7.1** The polygon field carries a **"Validate now"** button. Geometry and overlap
  checks (FR-2, FR-3) run **only** when it is pressed.
- **FR-4.7.2** Validation never runs implicitly on blur, on Next, or on each pass of
  `validateAllGroups()`. This is what retires RISK-1 and RISK-2: the expensive path is
  user-initiated and bounded.
- **FR-4.7.3** The button reports progress while running and cannot be double-fired.
- **FR-4.7.4** The field shows one of three states — **not yet validated**, **valid**, or
  **failed with reasons** — so the enumerator can always tell which.
- **FR-4.7.5** Editing the polygon after a successful validation returns the field to
  **not yet validated**. A stale pass must never be mistaken for a fresh one.
- **FR-4.7.6** **Submission requires a current, passing validation** for every non-empty
  `geoshape` answer. A polygon that was never validated blocks submit exactly as a failed
  one does — otherwise D7 becomes an opt-out from the whole feature.
- **FR-4.7.7** The submit-time gate reuses the **stored result** of the last validation run;
  it does not re-run the geometry work (NFR-2).

### FR-5 — Configuration

Revised after the ARF #192 finding. ARF established `extra.geoConfig` as the per-question geo
config namespace, and `Questions.extra` is a free-form `JSONField` already serialized to mobile
— so **no backend model change and no `config` table migration are required.**

**Placement decision**: `geoConfig` stays at **question level**, in `extra.geoConfig`, matching
the namespace ARF #192 already established with `accuracyThreshold`. Form-level placement was
considered and rejected — it would require a new `Forms` field, a migration, an addition to the
explicit `WebFormDetailSerializer.Meta.fields` allowlist, and a breaking change to ARF's
published question-level contract. Question level costs none of those.

#### FR-5.A — The complete `geoConfig` contract

Exactly **three** keys are authored in the form builder. Everything else is a hardcoded floor.

| Key | Type | Default | Configurable in arf-editor? |
|---|---|---|---|
| `accuracyThreshold` | number (m) | `15` | ✅ **Yes** — already exists in ARF #192 |
| `detectOverlaps` | boolean | `false` | ✅ **Yes** — master switch; also gates the geometry sync (FR-7) |
| `overlapThreshold` | number (%) | `20` | ✅ **Yes** — revealed only when `detectOverlaps` is ticked |

```json
"extra": {
  "geoConfig": {
    "accuracyThreshold": 15,
    "detectOverlaps": true,
    "overlapThreshold": 20
  }
}
```

#### FR-5.B — Always applied, never configurable

These are **validity floors, not policy**. A form cannot disable or loosen them, so they are
constants in code and never appear in `geoConfig` or in the builder UI:

| Rule | Value | Why it is not configurable |
|---|---|---|
| Value parses as a polygon | — | Garbage in means there is nothing to validate |
| Minimum vertices | `3` | Below 3 it is not a polygon, mathematically |
| No self-intersection | — | Area is ambiguous on a self-crossing ring |
| Minimum area | `10 m²` | 3.2 m × 3.2 m — catches accidental double-taps, below any real plot |

This is why there are **no** `validateShape` / `validateMinArea` / `minPoints` / `minAreaSqm`
keys: an enable-checkbox for "should this be a valid polygon?" has no meaningful *off* state.

- **FR-5.1** Overlap threshold is read from `extra.geoConfig.overlapThreshold`.
- **FR-5.2** Shape and minimum-area rules are fixed constants (FR-5.B), not read from config.
- **FR-5.3** Defaults when a question omits `geoConfig`: overlap 20% (D3), accuracy 15 m (ARF's
  default), `detectOverlaps` off. Defaults are applied client-side, so a device that has never
  re-synced still validates correctly.
- **FR-5.4** Question-level placement technically permits two polygon questions in one form to
  differ. No use case requires it; it is a consequence of the placement, not a feature.
- **FR-5.5** *(Q5 — answered: **yes, a UI is required**)* The form builder must offer a UI for
  authoring the three FR-5.A keys. Hand-edited form JSON is **not** acceptable.
  See FR-5.7.1 for where that UI lives.
- **FR-5.7** *(D13)* The `geoConfig` authoring UI is **`geoshape` only**. It does not appear on
  `geo`, on `geotrace`, or on any other question type — consistent with D6, which scopes all
  validation to `geoshape`. It writes **numeric** values into the structured `extra.geoConfig`
  object.
- **FR-5.8** Consequence of FR-5.7: a `geotrace` question cannot carry `geoConfig`. ARF's
  `TypeGeoDrawing` will fall back to its own default accuracy threshold (15 m) for geotrace
  capture, which is the behaviour it has today. Nothing regresses; geotrace simply gains no
  new configurability.

#### FR-5.7.1 — Where the UI lives: two options

The form builder is `akvo-react-form-editor@2.0.4`, imported wholesale by
[FormBuilderCreate.jsx:3](../../frontend/src/pages/form-builder/FormBuilderCreate.jsx#L3).
So this is **upstream work in the `akvo/akvo-react-form-editor` repo**, not akvo-mis frontend work.

**Option 1 — Extend `SettingGeo.jsx` upstream (recommended)**

The editor already has a per-type geo settings panel, already gated to exactly the three geo
types, and it already authors a structured value:

- `SettingGeo.jsx` is rendered for `[geo, geotrace, geoshape]` and today authors `center`
  using `InputNumber`, writing it as a structured array on the question.
- `center` is the **exact precedent**: authored in `SettingGeo` → persisted by the backend
  (`FormDetailQuestionSerializer` includes `extra` and `center`) → consumed by ARF
  `TypeGeoDrawing`. `geoConfig` should follow the identical path.

Cost: an upstream PR plus a version bump — the same workflow that delivered #192.

**Option 2 — Host-supplied `customParams` (no upstream change)**

`QuestionCustomParams.jsx` is a generic escape hatch: the host passes
`customParams={{ label, params: [...] }}` to `<WebformEditor>` and the editor renders inputs
for them. It works today with zero upstream change — but has three limitations that make it a
poor fit for `geoConfig`:

| Limitation | Evidence | Consequence |
|---|---|---|
| Writes to the question's **top level**, not nested | `updateGlobalStore` → `{ ...q, [objKey]: value }` | Produces `question.overlapThreshold`, **not** `extra.geoConfig.overlapThreshold` — FR-5.1/5.2 would have to be restated as flat keys |
| **Always wraps the value in an array**, and `type: 'input'` is a text `Input` | `const value = Array.isArray(val) ? val : [val]` | A threshold of 20 is stored as `["20"]` — a string in an array; the app must unwrap and coerce. No numeric input type exists |
| **Not type-scoped** — renders as a global "Custom Parameter" tab on every question | `QuestionDefinition.jsx:371` | Geo settings would appear on text, number and date questions too — violates FR-5.7 |

akvo-mis does not pass `customParams` today (no references in `frontend/src`), so Option 2 also
requires host-side wiring — it is not free either.

**Recommendation: Option 1.** It satisfies FR-5.7 as written, needs no unwrapping shim in the
app, and follows the `center` precedent exactly. Option 2 is the fallback if upstream changes
are blocked, and would force FR-5 to adopt flat, array-wrapped, string-typed keys.
- **FR-5.6** An out-of-range or malformed `geoConfig` value falls back to the default rather
  than disabling validation.

### FR-6 — Map review screen

- **FR-6.1** Reachable from the overlap error, showing the conflict geometrically.
- **FR-6.2** Current polygon in one colour, overlapping polygons in another (source docs:
  cyan / red).
- **FR-6.3** Viewport auto-fits all displayed polygons.
- **FR-6.4** Tapping a polygon shows that datapoint's name, so the enumerator can tell which
  farmer/record it belongs to (explicit in Scenarios 1 and 2).
- **FR-6.5** With connectivity, a satellite basemap loads beneath the polygons.
- **FR-6.6** Without connectivity, polygons still render — with a visible scale reference —
  and the screen states that imagery is unavailable offline.
- **FR-6.7** A disclaimer notes that satellite imagery may be outdated (ported from source).
- **FR-6.8** The screen is read-only. Edits happen back in the form field.

### FR-7 — Geometry index maintenance

- **FR-7.1** Polygon geometry and its bounding box are extractable for every datapoint of a
  form without parsing every `datapoints.json` blob at validation time.
- **FR-7.2** The index stays correct when a datapoint is created locally, edited locally,
  deleted, or arrives through datapoint sync.
- **FR-7.3** Existing installs with datapoints already on device are backfilled on migration.
- **FR-7.4** Forms with no `geoshape`/`geotrace` question incur no indexing work.

---

### FR-8 — Background auto-record *(D8)*

- **FR-8.1** Auto-record continues appending points when the app is backgrounded or the screen
  is locked, so an enumerator can pocket the phone while walking a boundary.
- **FR-8.2** While recording in the background, a **persistent notification** is shown, as
  Android requires for a location foreground service. It states that boundary recording is
  active and shows the current point count.
- **FR-8.3** Tapping the notification returns to the form and the polygon question.
- **FR-8.4** The notification offers **Stop recording** without navigating into the app.
- **FR-8.5** Background permission is requested **only when the enumerator first starts
  auto-record**, never at app launch, and the request explains why it is needed.
- **FR-8.6** If background permission is refused, auto-record still works in the foreground —
  the feature degrades, it does not fail. The enumerator is told recording will pause when the
  screen locks.
- **FR-8.7** The foreground service stops on: Stop pressed, leaving the question group,
  submitting, and app termination. **No path leaves the service running** (NFR-5).
- **FR-8.8** Points recorded while backgrounded are merged into the same ordered list in
  correct sequence, with no duplicates at the resume boundary.
- **FR-8.9** If the OS kills the app mid-recording, points already appended are not lost —
  they are recoverable through the existing form-draft mechanism.
- **FR-8.10** The accuracy filter (FR-1.4) applies identically in background and foreground.

## 5. Non-Functional Requirements

- **NFR-1 Performance** — Overlap check completes in <500 ms against 10,000 stored plots
  (source doc target). It runs on the JS thread inside form validation; it must not visibly
  stall navigation or submit.
- **NFR-2 Repeated validation** — `validateAllGroups()` re-validates every question of every
  group on submit. Overlap checks must not re-query the database once per group per submit.
- **NFR-3 Offline-first** — Every requirement except FR-6.5 works with the radio off. No
  degraded mode, no "sync first" prompt.
- **NFR-4 Storage** — Polygon geometry adds bounded, predictable storage per datapoint. No
  tile packs, no imagery cached on device (out of scope per D1).
- **NFR-5 Battery** — Vertex capture uses the same GPS acquisition pattern as `TypeGeo`;
  it does not hold a continuous high-accuracy location subscription for the whole form session.
- **NFR-6 Backward compatibility** — Forms without polygon questions behave exactly as today.
  Datapoints collected before this feature remain readable and syncable.
- **NFR-7 Accuracy** — Area and intersection maths are correct on a spheroid at plot scale
  (hectares); planar lat/lng arithmetic that treats degrees as metres is not acceptable.
- **NFR-8 Code style** — Airbnb ESLint as enforced in `app/`: no `for...of`, no `await` in
  loops, arrow-function components. Files stay within the 200–400 line guideline.
- **NFR-9 Testing** — Geometry maths (area, self-intersection, intersection ratio, threshold
  boundary) is unit-tested with known fixtures, independent of React Native rendering.

---

## 6. User Stories and Acceptance Criteria

### US-1 — Overlap with downloaded data *(source Scenario 1)*
> As a field enumerator, I want a plot that overlaps previously downloaded data to be caught
> offline, so I fix it before submitting.

- **AC-1.1** Given the form's datapoints were synced to the device before signal was lost,
  when I capture a polygon overlapping one of them by ≥ threshold, then validation fails.
- **AC-1.2** The error names both my datapoint and the conflicting one, per FR-4.1.
- **AC-1.3** I can open the map review screen and see both polygons and their overlap.
- **AC-1.4** Tapping either polygon shows whose record it is.
- **AC-1.5** I cannot submit until it is resolved.
- **AC-1.6** All of the above works with no connectivity. *(Except the satellite basemap — D4.)*

### US-2 — Overlap with unsubmitted local data *(source Scenario 2)*
> As a field enumerator, I want a plot overlapping a record I collected but have not yet
> uploaded to be caught, so two overlapping plots never leave the device.

- **AC-2.1** Given a datapoint saved on this device with `syncedAt IS NULL`, when I capture an
  overlapping polygon in a new submission of the same form, then validation fails.
- **AC-2.2** This holds whether the earlier record is a saved draft or a submitted-but-unsynced
  datapoint.
- **AC-2.3** If I reopen and edit the *earlier* record and re-run validation there, the newer
  record is treated as an existing plot — the check is symmetric.
- **AC-2.4** Editing a record does not report it as overlapping itself (FR-3.2).

### US-3 — Overlap resolved *(source Scenario 3)*
- **AC-3.1** Given I redraw the boundary below the threshold, when I re-run validation, no
  error is shown.
- **AC-3.2** The stale error message is gone, not merely superseded.
- **AC-3.3** Submission proceeds.

### US-4 — Invalid geometry
- **AC-4.1** Fewer than 3 vertices → FR-2.2 message; submission blocked.
- **AC-4.2** Area below the configured minimum → FR-2.3 message; submission blocked.
- **AC-4.3** Self-crossing boundary → FR-2.4 message; submission blocked.
- **AC-4.4** Each message identifies which question failed.

### US-5 — Capture experience *(ARF #192 parity)*
- **AC-5.1** I can add a point by tapping the map, by dragging a marker and pressing Record,
  or by starting auto-record and walking the boundary.
- **AC-5.2** In auto-record I see the point count grow on the interval, and a live GPS marker
  distinct from the recorded points.
- **AC-5.3** In auto-record, fixes worse than the accuracy threshold are silently skipped and
  the count does not advance — I can see the current accuracy and understand why.
- **AC-5.4** When the form sets `extra.geoConfig.accuracyThreshold`, I see it as a read-only
  value and cannot change it.
- **AC-5.5** I can undo the last point, remove any single point, or clear everything —
  clearing more than 3 points asks me to confirm.
- **AC-5.6** I see the enclosed area once ≥3 points exist on a `geoshape`.
- **AC-5.7** Leaving and returning to the question group preserves captured points.
- **AC-5.8** I never manually re-capture the first point to close the ring.
- **AC-5.9** Stopping auto-record, leaving the group, or backgrounding the app stops the GPS
  watch — my battery is not drained by a forgotten subscription. *(Backgrounding behaviour
  pending Q3b.)*

### US-6 — Existing forms keep working
- **AC-6.1** A form with no polygon question behaves identically to today.
- **AC-6.2** A `geoshape` question no longer renders as a text input.
- **AC-6.3** Datapoints created before this feature still open, edit, and sync.

---

## 7. Out of Scope

| Excluded | Reason |
|---|---|
| Offline satellite tile packs / download-by-region UI | D1 |
| Mapbox or any new native map module | D4 |
| Cross-form overlap detection | D2 — same form only |
| Region/administration filtering of candidates | FR-3.3 — explicitly harmful |
| Server-side overlap validation on submit | Offline-first; the device is authoritative at collection time |
| `plots` table with `isDraft` / `instanceName` matching | Section 1 — solves a problem Akvo MIS does not have |
| Intent contract, XLSForm appearance changes | Section 1 — no external app involved |
| Web frontend polygon capture | Already works via ARF 2.7.9 + editor 2.0.4 — nothing to build (§2, Q9) |
| Web frontend polygon *validation* (area, self-intersection, overlap) | Mobile-only request. Web has capture but no validation; parity is a later decision |
| Web manage-data display of polygon answers | FR-1.17 — optional, independent |
| Overlap detection between two polygons *within a single submission* | Not in source AC; confirm if repeatable groups can hold polygons |

---

## 8. Dependencies and Risks

| # | Item | Impact |
|---|---|---|
| DEP-1 | ~~Backend config payload change~~ — **dissolved** by the `extra.geoConfig` finding. Remaining: **an upstream PR to `akvo-react-form-editor`** for the `geoConfig` UI (D13, FR-5.7.1) | Reduced from a schema change to an authoring-surface change — but now in a **separate repo** with its own release cycle. Backend round-trip already works: `FormDetailQuestionSerializer` includes `extra` |
| DEP-2 | A geometry library must be chosen (area, self-intersection, polygon intersection on a spheroid) | **Strong candidate already in the repo**: `@turf/turf ^6.5.0` is a declared frontend dependency and is pure JS, so it runs in React Native. Covers all four needs — `area` (geodesic, satisfies NFR-7), `kinks` (self-intersection), `intersect` (+`area` for the ratio), `bbox` (FR-7). Import the scoped submodules (`@turf/area` etc.), **not** the full `@turf/turf` bundle — mobile bundle size (NFR-4). ARF supplies no geometry maths, so this is the one genuinely new dependency |
| DEP-3 | Local SQLite schema migration for the geometry index (FR-7) | Migration path for existing installs, see FR-7.3 |
| DEP-4 | ARF `TypeGeoDrawing` is the upstream of the ported capture code | Divergence risk: fixes landing in ARF will not flow to `app/` automatically. Value format is the contract that must not drift |
| RISK-1 | ~~JS-thread geometry maths inside form validation~~ — **largely retired by D7**: the work is user-initiated, one polygon at a time, with a progress indicator | Residual: a single check over 10,000 plots must still meet NFR-1 |
| RISK-2 | ~~`validateAllGroups()` fan-out~~ — **retired by D7/FR-4.7.7**: submit reads the stored result instead of re-running geometry | — |
| RISK-7 | Background location permission is separately grantable and commonly refused | FR-8.6 requires graceful degradation, not failure |
| RISK-8 | Foreground service left running drains battery | FR-8.7 enumerates every stop path; the most likely field complaint if missed |
| RISK-9 | D7's explicit trigger makes "never validated" a reachable state | FR-4.7.5/4.7.6 close it; without them D7 is an opt-out from the feature |
| RISK-3 | Satellite imagery unavailable offline contradicts the literal wording of Scenarios 1 and 2 | Accepted under D4; see Q1 |
| RISK-4 | GPS drift at plot boundaries generates false positives | Mitigated by the 20% threshold and FR-5 configurability |
| RISK-5 | Enumerators walking large plots produce high vertex counts | Auto-record at 10 s intervals (FR-1.3c) makes this likely, not hypothetical: a 30-minute walk yields ~180 points. Affects storage, index size, and intersection cost |
| RISK-6 | RN ↔ WebView `postMessage` bridge for coordinates (§3.1) | Has no ARF precedent — ARF's Leaflet runs in the same JS context. Genuinely new surface, and the most likely source of dropped or duplicated points |

---

## 9. Open Questions

**Q1 — Satellite imagery offline — TRACKED SEPARATELY.** Three paths costed, with a
recommendation and named decision owners, in
[offline-satellite-imagery-plan.md](./offline-satellite-imagery-plan.md). Decision still open,
but it blocks nothing else in this spec: the current text (D1, D4, FR-6.6) already describes
the recommended Path A.

**Q2 — Does overlap validation apply to `geotrace`?** *(narrowed by ARF)* ARF settles the
value format: both types are the same `[[lat,lng],…]` array, differing only in rendering and
min-point count. So the remaining question is policy, not format — should a `geotrace` be
treated as an implicitly closed ring for overlap purposes, or is overlap detection
`geoshape`-only? FR-2.6 currently exempts geotrace from area and self-intersection.

**Q3 — ~~Capture method~~ — ANSWERED by ARF #192.** All three modes ship: tap, manual marker,
and auto-record (FR-1.3). No decision needed.

**Q3b — Does auto-record survive backgrounding?** ARF runs in a browser tab where this is
moot. On Android, an enumerator walking a boundary will lock the screen or switch apps.
Should auto-record continue in the background — which means a foreground service and a
notification — or pause and resume?

**Q4 — When does validation fire?** On leaving the question, on pressing Next, only on final
submit, or on an explicit "Check for overlaps" button? This drives RISK-1/RISK-2 directly.
A button is cheapest and most predictable; automatic is smoother but runs the query far more often.

**Q5 — ~~Threshold configurability scope~~ — FULLY RESOLVED.** Per-question via
`extra.geoConfig` (FR-5), following ARF's `accuracyThreshold` precedent. A **form-builder UI is
required** (D13); hand-edited JSON is not acceptable. It belongs upstream in
`akvo-react-form-editor`'s `SettingGeo.jsx` — see FR-5.7.1 for why the generic `customParams`
escape hatch is the weaker option.

**Q9 — ~~Should akvo-mis web adopt ARF `TypeGeoDrawing`~~ — CLOSED.** The premise was wrong:
web already collects polygons end to end via `akvo-react-form-editor@2.0.4` (authoring) and
ARF 2.7.9 (rendering), with no frontend code required (§2). Whether a given form has a polygon
question is a **form-authoring choice**, per form, made in the builder. This work makes the
mobile client capable of the same thing; it does not restrict either client. Optional web
display parity is FR-1.17.

**Q10 — Should the ported capture code stay in sync with ARF?** DEP-4. Options: hard fork and
accept drift, or track ARF releases and re-port. The value format is the contract that must
not diverge either way.

**Q6 — Polygons in repeatable groups.** Can a repeatable question group contain a polygon
question? If so, two polygons in one submission may overlap each other — not covered by any
source AC (Section 7).

**Q7 — Monitoring forms.** Akvo MIS monitoring forms pre-fill from a parent submission. If a
monitoring form re-captures the plot boundary, should it be checked against its own parent
datapoint — which will overlap almost completely by design?

**Q8 — Deleted and rejected datapoints.** Should a datapoint that was rejected in approval, or
soft-deleted, still block a new plot?

---

## 10. Traceability to Sources

### 10.1 akvo-react-form #192 (`TypeGeoDrawing`)

| ARF capability | Disposition |
|---|---|
| `[[lat,lng],…]` answer format | **Adopted verbatim** — FR-1.2; the cross-client contract |
| geotrace = Polyline, geoshape = Polygon | Adopted — FR-1.1 |
| Min points: 2 / 3 | Adopted — FR-1, and consistent with FR-2.2 |
| `extra.geoConfig.accuracyThreshold` | Adopted **and extended** — FR-5 adds `overlapThreshold`, `minAreaSqm` |
| Tap / manual / auto-record modes | Adopted — FR-1.3 |
| Accuracy-filtered auto-record, 10 s interval | Adopted — FR-1.4 |
| Undo / clear / remove-single-point, confirm above 3 points | Adopted — FR-1.7 |
| Get My Location (recentre, no point appended) | Adopted — FR-1.10 |
| FitBounds except while recording | Adopted — FR-1.9 |
| `geoDrawing*` i18n keys (en/id/in/fr/de) | Adopted — FR-1.15; translations transfer |
| 5-way `src/support/` component split | Adopted with changes — §3.1; three collapse into the WebView |
| Leaflet as the map stack | Adopted — reinforces D4 |
| antd `Modal`, `Form.useWatch`, `form.setFieldsValue` | **Replaced** — RN `Alert`, `FormState` (§3.1) |
| `navigator.geolocation` | **Replaced** — `expo-location` / existing `loc` wrapper |
| Area calculation | **Absent in ARF** — new, FR-1.8 |
| Self-intersection, min-area, overlap validation | **Absent in ARF** — from the reference validator, FR-2/FR-3 |

### 10.2 Reference validator docs

| Source requirement | Disposition |
|---|---|
| Vertex/area/self-intersection checks | Ported — FR-2 |
| Bounding-box pre-filter then precise geometry | Ported — FR-3.4 |
| Region as metadata only, never a filter | Ported — FR-3.3 |
| `New plot for X overlaps with plot for Y` | Ported — FR-4.1 |
| Fully offline, no sync between plots | Ported — FR-3.7 |
| Map with current/overlap polygons, tap for name | Ported — FR-6 |
| Imagery disclaimer banner | Ported — FR-6.7 |
| 20% vs 5% threshold conflict | **Resolved** — D3, configurable, default 20% |
| `plots` table, `isDraft`, `instanceName` matching | **Dropped** — `datapoints` already serves this |
| Intent extras (`shape`, `plot_name`, `region`, `sub_region`) | **Dropped** — no external app |
| `RESULT_OK value=null` blocking mechanism | **Replaced** — existing `feedback` + submit gate |
| XLSForm appearance changes | **Dropped** |
| Mapbox SDK, offline tile packs, `MAPBOX_DOWNLOADS_TOKEN` | **Dropped** — D1, D4 |
| Google Maps FAB (online, fresher imagery) | **Deferred** — not in confirmed scope; cheap to add later |
| Sync extraction from `rawData` farmer-name fields | **Replaced** — `generateDataPointName` already does this |

---

## 11. Q1 — Offline Satellite Imagery

**Moved to its own document**: [offline-satellite-imagery-plan.md](./offline-satellite-imagery-plan.md)

It is a product/procurement decision rather than an engineering one, and it gates nothing else
in this spec — so it is tracked separately to keep this document decidable on its own.

Summary of that plan:

| Path | Offline basemap | Licensing | Keeps D4 / §3.1 |
|---|---|---|---|
| **A** — polygons only | ❌ blank canvas + scale bar | None | ✅ |
| **B** — pre-downloaded tile packs | ✅ | ⚠️ **blocking** | ✅ |
| **B′** — native map SDK | ✅ | ⚠️ **blocking** | ❌ rewrite of FR-6 |

**Recommendation: ship Path A, build the tile-resolver seam, decide B vs B′ in parallel.**
Imagery is a comprehension aid, not a correctness input — FR-2, FR-3 and FR-4 are identical
across all three paths. The current spec (D1, D4, FR-6.6) already describes Path A.

**One cross-reference worth carrying back here**: D8 forces a development build (§3.2), so the
"we'd need a dev client" objection to a native map SDK is **already spent**. If Q1 is ever
reopened, B′ must be re-argued on licence cost and rewrite scope alone — not on D4's original
build-tooling reasoning.
