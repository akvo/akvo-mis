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

Key implementation:
1. `useParams()` → `formId`.
2. On mount:
   - `GET /api/v1/manage/forms/${formId}` → `apiToEditor()` → `apiData`
   - Check localStorage draft: if `draft.savedAt > apiData.savedAt`, use draft
   - `setInitialValue(draft || apiData)`
   - Store `formStatus`, `formVersion`, `formLatestVersion` in state
3. Published form info banner: `formStatus === "published"`:
   - If `formLatestVersion > formVersion`: "Changes saved as snapshot v{latest_version}. Click Publish to activate."
   - Else: "Editing a published form creates a new version snapshot. Click Publish to activate."
4. On save (PUT):
   - `editorToApi(editorRef.current)` → `PUT /api/v1/manage/forms/${formId}`
   - On `200`: `message.success`, remove localStorage draft, update `formLatestVersion` from response
5. On publish (`POST .../publish`):
   - On `200`: `message.success("Form published")`, update `formStatus`, `formVersion`, `formLatestVersion` from response
6. On unpublish (`POST .../unpublish`):
   - Show `formStatus === "published"` only
   - On `200`: `message.success("Form unpublished")`, update `formStatus` to `"draft"`
7. Debounce auto-save to `form-builder-draft-${formId}`.

Button visibility rules:

| Button | Show when |
|---|---|
| Save | Always |
| Publish | `can("publish", "form-builder")` AND (`status === "draft"` OR `latest_version > version`) |
| Unpublish | `can("publish", "form-builder")` AND `status === "published"` |

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
