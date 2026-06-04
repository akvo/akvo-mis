# Implementation Plan: Form Builder Frontend Integration (FB-003)

**Issue**: #228
**Branch**: `feature/228-integrate-akvo-react-form-editor-in-frontend`
**Estimated effort**: 3–4 days (frontend only)
**Prerequisite**: FB-002A merged and available in dev environment

---

## Prerequisites

- [x] FB-002A (`feature/229-fb-002-implement-backend-form-crud-api`) merged — provides:
  - `POST /api/v1/manage/forms` (create)
  - `GET /api/v1/manage/forms` (list)
  - `GET /api/v1/manage/forms/{id}` (retrieve from latest snapshot for published forms)
  - `PUT /api/v1/manage/forms/{id}` (draft: in-place; published: snapshot-only)
  - `POST /api/v1/manage/forms/{id}/publish`
  - `POST /api/v1/manage/forms/{id}/unpublish`
  - `POST /api/v1/manage/forms/{id}/activate/{version_id}` (FB-003B)
- [x] Editor emits `"image"` for photo questions — no alias needed in transformer
- [ ] Verify editor component API from `node_modules` (component name, `onChange` prop signature):
  ```bash
  cat frontend/node_modules/akvo-react-form-editor/package.json | grep '"main"\|"module"\|"version"'
  ls frontend/node_modules/akvo-react-form-editor/dist/
  ```
- [ ] Backend services running: `./dc.sh up -d`

---

## Task Breakdown

Tasks in the same group can run in parallel. Each group should be a single commit.

---

### Group A: Frontend — ability.js  *(backend already done in FB-002A)*

**Requirements**: FR-1

The `can_form_builder()` property and `UserRoleSerializer` field are **already implemented** in FB-002A (`v1_profile/models.py:243`, `v1_users/serializers.py:686`). No backend work needed.

**File**: `frontend/src/components/can/ability.js`

After line `const can_invite_user = ...`, add:

```javascript
const can_form_builder = roles.filter((r) => r?.can_form_builder).length > 0;
```

After the `can_invite_user` block, add:

```javascript
if (can_form_builder) {
  can("manage", "form-builder");
}
```

**Verify**:
```bash
./dc.sh exec -T frontend npx eslint src/components/can/ability.js
```

---

### Group B: Frontend — Transformer Library

**Requirements**: FR-5

**File**: `frontend/src/lib/form-builder-transform.js`

```javascript
// ── helpers ──────────────────────────────────────────────────────────────────

const _camelToSnake = (obj) => {
  const result = {};
  for (const key of Object.keys(obj)) {
    const snakeKey = key.replace(/([A-Z])/g, "_$1").toLowerCase();
    result[snakeKey] = obj[key];
  }
  return result;
};

const _snakeToCamel = (obj) => {
  const result = {};
  for (const key of Object.keys(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
    result[camelKey] = obj[key];
  }
  return result;
};

// "entity" must be converted to "cascade" — the backend rejects "entity" directly
const EDITOR_TYPE_ALIASES = { entity: "cascade" };

const _resolveEditorType = (typeStr, question) => {
  if (typeStr === "cascade" && question.extra?.type === "entity") {
    return "entity";
  }
  return typeStr;
};

// ── public API ────────────────────────────────────────────────────────────────

export const editorToApi = (editorOutput) => {
  const { name, type, question_group } = editorOutput;
  return {
    name,
    type: type || "registration",
    question_group: (question_group || []).map((group, gi) => ({
      id: group.id || null,
      name: group.name,
      label: group.label || null,
      order: gi + 1,
      repeatable: group.repeatable || false,
      repeat_text: group.repeat_text || null,
      question: (group.question || []).map((q, qi) => {
        const s = _camelToSnake(q);
        return {
          id: s.id || null,
          order: qi + 1,
          label: s.label,
          short_label: s.short_label || null,
          name: s.name || null,
          type: EDITOR_TYPE_ALIASES[s.type] || s.type,
          meta: s.meta || false,
          required: s.required !== false,
          rule: s.rule || null,
          dependency: s.dependency || null,
          dependency_rule: s.dependency_rule || "AND",
          api: s.api || null,
          extra: s.extra || null,
          tooltip: s.tooltip || null,
          fn: s.fn || null,
          pre: s.pre || null,
          display_only: s.display_only || false,
          option: (s.option || []).map((opt, oi) => ({
            order: oi + 1,
            label: opt.label,
            value: opt.value || String(opt.label).toLowerCase().replace(/\s+/g, "_"),
            other: opt.other || false,
            color: opt.color || null,
          })),
        };
      }),
    })),
  };
};

export const apiToEditor = (apiResponse) => {
  const {
    id, name, type, version, latest_version, status, published_at,
    active_version_id, question_group,
  } = apiResponse;
  return {
    id, name, type, version, latest_version, status, published_at,
    active_version_id,
    question_group: (question_group || []).map((group) => ({
      id: group.id,
      name: group.name,
      label: group.label,
      repeatable: group.repeatable,
      repeat_text: group.repeat_text,
      question: (group.question || []).map((q) => {
        const c = _snakeToCamel(q);
        return {
          ...c,
          type: _resolveEditorType(c.type, c),
          option: (q.option || []).map((opt) => ({
            order: opt.order,
            label: opt.label,
            value: opt.value,
            other: opt.other,
            color: opt.color,
          })),
        };
      }),
    })),
  };
};
```

**Verify**:
```bash
cd frontend && node -e "
  const t = require('./src/lib/form-builder-transform');
  const out = t.editorToApi({
    name: 'Test', type: 'registration',
    question_group: [{ id: null, name: 'g', label: 'G', order: 1, repeatable: false,
      question: [{ id: null, order: 1, label: 'Q', type: 'input', displayOnly: true, pre: {} }]
    }]
  });
  const q = out.question_group[0].question[0];
  console.assert(q.display_only === true, 'displayOnly must be converted');
  console.assert(q.pre === null, 'pre: {} must become null');
  console.log('OK', JSON.stringify(q));
"
```

---

### Group C: Frontend — FormBuilderList.jsx

**Requirements**: FR-2

**File**: `frontend/src/pages/form-builder/FormBuilderList.jsx`

Key implementation:
- `GET /api/v1/manage/forms` on mount (paginated; reads `response.data.data` array)
- Table columns: Name, Type, Status (Draft/Published badge), Actions (Edit link)
- "New Form" button → `/control-center/form-builder/create`
- Edit action → `/control-center/form-builder/${record.id}/edit`
- Ant Design `Skeleton` loading state, `Empty` when empty

Status badge colours: `Draft → default (grey)`, `Published → green`

---

### Group D: Frontend — FormBuilderCreate.jsx

**Requirements**: FR-3

**File**: `frontend/src/pages/form-builder/FormBuilderCreate.jsx`

Key implementation:
1. Verify editor component name and props from `node_modules` before writing.
2. Track editor state via `onChange` into a `useRef` — avoids re-render on every keystroke.
3. Debounce auto-save with `setTimeout`/`clearTimeout` (no lodash).
4. On save:
   - `editorToApi(editorRef.current)` → `POST /api/v1/manage/forms`
   - Navigate to `/control-center/form-builder/${response.data.id}/edit`
   - `localStorage.removeItem("form-builder-draft-new")`
5. Draft restore on mount: check `localStorage.getItem("form-builder-draft-new")`.

Draft storage format:
```json
{ "value": { ...editorOutput }, "savedAt": "2026-06-01T10:00:00.000Z" }
```

---

### Group E: Frontend — FormBuilderEdit.jsx

**Requirements**: FR-4, FR-6, FR-7

**File**: `frontend/src/pages/form-builder/FormBuilderEdit.jsx`

Key notes:
- `loadForm` is wrapped in `useCallback([formId])` — satisfies `react-hooks/exhaustive-deps` without any lint-disable comment
- **Stale draft fix**: draft JSON now includes `formVersion`; on load, reject draft if `typeof draft.formVersion !== "undefined" && draft.formVersion !== apiData.version`; silently remove stale draft from localStorage. Avoids `draft.formVersion !== undefined` to satisfy `no-undefined` ESLint rule.
- **`onSave` draft**: `localStorage.setItem(..., JSON.stringify({ value, savedAt, formVersion }))` — stores current `formVersion` for stale detection.
- **`onResetDraft`**: clears localStorage draft, sets `initialValue = null`, calls `loadForm(true)` (skip draft check) — wired to "Load from server" button in `FormEditorBanners`.
- **`onSave`** → `PUT /manage/forms/{formId}` → update `formStatus`, `formVersion`, `formLatestVersion` from response
- Info banner: snapshot pending vs. fresh-publish text depends on `formLatestVersion > formVersion`
- Publish button shown when `formStatus === "draft"` OR `hasPendingSnapshot`
- Unpublish button shown when `formStatus === "published"` (behind Popconfirm)

---

## Testing Requirements

### Frontend

Add to `frontend/src/pages/form-builder/__test__/`:

| Test | What it verifies |
|---|---|
| `ability.test.js` | `can_form_builder: true` → `can("manage", "form-builder")` |
| `form-builder-transform.test.js` | `editorToApi` camelCase→snake_case, `pre:{}`→null, type aliases, order recalculation |
| `form-builder-transform.test.js` | `apiToEditor` snake_case→camelCase, entity/cascade resolution, `latest_version` passthrough |
| `FormBuilderList.test.jsx` | Renders form rows with status badge; "New Form" navigates |
| `FormBuilderCreate.test.jsx` | Save success: message shown, navigates to `response.data.id` |
| `FormBuilderCreate.test.jsx` | Save error: error message shown |
| `FormBuilderEdit.test.jsx` | Loads form data; shows info banner when `status="published"` |
| `FormBuilderEdit.test.jsx` | 200 save response: stays on same page, updates `latest_version`, clears localStorage |
| `FormBuilderEdit.test.jsx` | Publish success: updates status and version state |
| `FormBuilderEdit.test.jsx` | Unpublish success: status changes to draft, Unpublish button hides |

Run:
```bash
cd frontend && CI=true npm test -- --testPathPattern="form-builder"
```

---

---

### Group G: Version Preview ✅

#### G-1: Backend — New `version_detail` action

**File**: `backend/api/v1/v1_forms/views.py`

Add a new `@action` to `FormBuilderViewSet`:

```python
@extend_schema(
    tags=["Manage Forms"],
    summary="Get a single published version snapshot with schema",
)
@action(
    detail=True,
    methods=["get"],
    url_path=r"versions/(?P<version_id>[^/.]+)",
)
def version_detail(self, request, version_id=None, *args, **kwargs):
    form = self.get_object()
    pv = get_object_or_404(form.published_versions, pk=version_id)
    data = FormPublishedVersionSerializer(pv).data
    data["schema"] = pv.schema
    return Response(data)
```

**File**: `backend/api/v1/v1_forms/urls.py`

Add before the existing `versions$` pattern:

```python
re_path(
    r"^(?P<version>(v1))/manage/forms/(?P<pk>[0-9]+)"
    r"/versions/(?P<version_id>[0-9]+)$",
    FormBuilderViewSet.as_view({"get": "version_detail"}),
),
```

No migration needed — reads existing `FormPublishedVersion.schema` field.

#### G-2: Frontend — `FormBuilderEdit.jsx` changes

**New state**:
```javascript
const [previewingVersion, setPreviewingVersion] = useState(null); // { id, version } or null
const [previewLoadingId, setPreviewLoadingId] = useState(null);
```

**`onPreview` handler** (null-first pattern forces editor remount):
```javascript
const onPreview = (record) => {
  setPreviewLoadingId(record.id);
  const prevValue = initialValue;   // save for error recovery
  setInitialValue(null);            // unmount editor immediately
  api.get(`/manage/forms/${formId}/versions/${record.id}`)
    .then((res) => {
      const schema = res.data.schema;
      setInitialValue(apiToEditor({
        ...schema,
        id: Number(formId),
        status: formStatus,
        latest_version: formLatestVersion,
        active_version_id: null,
      }));
      setPreviewingVersion({ id: record.id, version: record.version });
      setDrawerOpen(false);
    })
    .catch((err) => {
      const msg = err.response?.data?.message || text.formBuilderPreviewError;
      notify({ type: "error", message: msg });
      setInitialValue(prevValue);   // restore on error
    })
    .finally(() => {
      setPreviewLoadingId(null);
    });
};
```

**`onExitPreview` handler**:
```javascript
const onExitPreview = () => {
  setPreviewingVersion(null);
  setInitialValue(null);
  loadForm(true);
};
```

**Preview banner** (shown above `infoBannerText`):
```jsx
{previewingVersion && (
  <Alert
    type="warning"
    message={`Previewing snapshot v${previewingVersion.version} — not the saved state.`}
    action={<Button size="small" onClick={onExitPreview}>Back to saved</Button>}
    style={{ marginBottom: 8 }}
    showIcon
  />
)}
```

**versionColumns changes**:
- Active row: `rowClassName={(r) => (r.is_active ? "version-row-active" : "")}`
- Preview button added to Actions column for non-active rows (alongside Set Active)
- `previewLoadingId` drives the spinner

**style.scss** — add active row highlight:
```scss
.ant-table-row {
  &.version-row-active {
    background-color: #f6ffed;
  }
}
```

---

### Group I: Reusable Components ✅

**Directory**: `frontend/src/pages/form-builder/components/`

Three sub-components extracted from the page files:

| Component | Extracted from | Purpose |
|---|---|---|
| `FormStatusTag` | `FormBuilderList` columns | Published/Draft tag |
| `FormEditorBanners` | `FormBuilderCreate` + `FormBuilderEdit` | Draft restored / Preview / Info alerts |
| `VersionHistoryDrawer` | `FormBuilderEdit` | Drawer + Table + Activate/Preview actions |

**`FormStatusTag`** props: `{ status, text }`

**`FormEditorBanners`** props: `{ draftRestored, onDismissDraft, previewingVersion?, onExitPreview?, infoBannerText?, text, topSpacing? }`
- `topSpacing=true` adds `marginTop:16` to the first alert (Create page context)
- Optional props render nothing when absent

**`VersionHistoryDrawer`** props: `{ open, onClose, versions, loading, onRefresh, activatingId, previewLoadingId, onActivate, onPreview, text }`

New `ui-text.js` keys added: `formBuilderStatusPublished`, `formBuilderStatusDraft`, `formBuilderResetDraft`

**`FormEditorBanners` additional prop**: `onResetDraft` — when provided, renders a "Load from server" `<Button size="small">` as the `action` of the draft-restored Alert. Clears localStorage draft and reloads from API.

**`VersionHistoryDrawer` pagination**: `{ pageSize: 10, hideOnSinglePage: true }` — client-side pagination handles 99+ versions; Ant Design hides the pagination bar automatically when ≤10 rows.

---

### Group J: Backend — Tests for `version_detail` Endpoint ✅

**File**: `backend/api/v1/v1_forms/tests/tests_manage_form_versions.py`

10 tests in `ManageFormVersionDetailTestCase` covering `GET /api/v1/manage/forms/{id}/versions/{version_id}`:

| Test | Assertion |
|---|---|
| `test_version_detail_returns_200_with_all_fields` | 200 + all 6 fields present (`id`, `version`, `published_at`, `published_by`, `is_active`, `schema`) |
| `test_version_detail_schema_contains_question_group` | `schema` is a non-empty dict with a `question_group` list |
| `test_version_detail_published_by_is_admin_email` | `published_by` resolves to publishing user's email |
| `test_version_detail_is_active_true_for_active_version` | `is_active=True` for the active version |
| `test_version_detail_is_active_false_for_pending_snapshot` | PUT-created snapshot: `is_active=False`; original v1 stays `is_active=True` |
| `test_version_detail_404_for_nonexistent_form` | 404 when form doesn't exist |
| `test_version_detail_404_for_nonexistent_version` | 404 when version_id doesn't belong to the form |
| `test_version_detail_404_version_from_different_form` | 404 when version_id belongs to a sibling form |
| `test_version_detail_requires_authentication` | 401 with no auth header |
| `test_version_detail_any_version_retrievable_by_id` | v1 and v2 independently retrievable after two publish cycles |

---

## Lint & Prettier

Run before every commit:
```bash
./dc.sh exec -T frontend yarn lint
./dc.sh exec -T frontend yarn prettier
```

---

## Implementation Order

```
Day 1: Group A (ability.js) + Group B (transformer lib + tests)
Day 2: Group C (list page) + Group D (create page)
Day 3: Group E (edit page with publish/unpublish)
Day 4: Edit page tests + all lint/prettier
```
