# Implementation Plan: Form Builder Frontend Integration (FB-003)

**Issue**: #228
**Branch**: `feature/228-integrate-akvo-react-form-editor-in-frontend`
**Status**: ✅ Implemented

---

## Prerequisites

- [x] FB-002A (`feature/229-fb-002-implement-backend-form-crud-api`) merged — provides all manage endpoints
- [x] Editor component verified: `WebformEditor` (default export), uses `onSave` callback — **no `onChange` event**
- [x] Backend services running: `./dc.sh up -d`

---

## Task Breakdown

---

### Group A: Frontend — ability.js ✅

**File**: `frontend/src/components/can/ability.js`

Added after `can_invite_user`:

```javascript
const can_form_builder =
  roles.filter((r) => r?.can_form_builder).length > 0;

if (can_form_builder) {
  can("manage", "form-builder");
}
```

---

### Group B: Frontend — Transformer Library ✅

**File**: `frontend/src/lib/form-builder-transform.js`

Key implementation notes:
- Helpers use `Object.keys().forEach()` (ESLint `no-restricted-syntax` forbids `for...of`)
- `_snakeOrNull(label)` generates a fallback snake_case name from label
- `pre` normalization: `s.pre && Object.keys(s.pre).length > 0 ? s.pre : null` (handles `{}`)
- `delete s.question_group_id` removes editor-internal field before sending to backend
- Group `repeat_text` handles both camelCase alias (`repeatText`) and snake_case from editor

```javascript
export const editorToApi = (editorOutput) => {
  const { name, description, question_group } = editorOutput;
  return {
    name: name || "",
    description: description || null,
    question_group: (question_group || []).map((group, gi) => ({
      id: group.id || null,
      name: group.name || _snakeOrNull(group.label),
      label: group.label || null,
      order: gi + 1,
      repeatable: group.repeatable || false,
      repeat_text: group.repeatText || group.repeat_text || null,
      question: (group.question || []).map((q, qi) => {
        const s = _camelToSnake(q);
        delete s.question_group_id;
        return {
          id: s.id || null,
          order: qi + 1,
          label: s.label,
          short_label: s.short_label || null,
          name: s.name || _snakeOrNull(s.label),
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
          pre: s.pre && Object.keys(s.pre).length > 0 ? s.pre : null,
          display_only: s.display_only || false,
          option: (s.option || []).map((opt, oi) => ({ ... })),
        };
      }),
    })),
  };
};
```

---

### Group C: Frontend — FormBuilderList.jsx ✅

**File**: `frontend/src/pages/form-builder/FormBuilderList.jsx`

- `GET /manage/forms?page={n}` on mount and on page change
- Table: Name, Type (`parent === null` → "Registration"), Status badge (green/grey), Edit button
- "New Form" button navigates to `/control-center/form-builder/create`
- `Spin` loading state (not Skeleton); `Empty` when no forms

---

### Group D: Frontend — FormBuilderCreate.jsx ✅

**File**: `frontend/src/pages/form-builder/FormBuilderCreate.jsx`

Key notes:
- `initialValue` starts as `null`; on mount checks localStorage and sets `{}` or draft value
- Editor renders only after `initialValue !== null` (prevents FOUC with `<Spin>` guard)
- **`onSave` callback** (not `onChange` + useRef): the editor triggers `onSave(editorOutput)` when its built-in Save button is clicked; the callback runs `editorToApi → POST → navigate`
- Draft written to localStorage (2 s debounce) inside `onSave` before the API call
- Passing `onSave={null}` while `saving === true` prevents double-submission

---

### Group E: Frontend — FormBuilderEdit.jsx ✅

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

### Group F: Frontend — Version History Drawer ✅

**File**: `frontend/src/pages/form-builder/FormBuilderEdit.jsx` (same file as Group E)

- "Versions" button (`HistoryOutlined`) → opens `Drawer`, fetches `GET /manage/forms/{id}/versions` lazily
- Table: Version (+ Active badge), Published At, Published By, Set Active
- "Set Active" → `Popconfirm` → `POST /manage/forms/{id}/activate/{version_id}`
- After activation: close drawer, clear localStorage draft, set `initialValue = null`, call `loadForm(true)` to remount editor with activated content
- `activatingId` state disables all other Activate buttons while one is in flight

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

```bash
./dc.sh exec -T frontend yarn lint
./dc.sh exec -T frontend yarn prettier
```

Both pass with zero errors.
