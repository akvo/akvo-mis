# Cascading Lists, Tree Hierarchy & Entity Selectors

This document covers hierarchical dropdowns, tree selectors, and dynamic entity linking in `akvo-react-form` and `akvo-react-form-editor` (source: `akvo-react-form/README.md#cascade-any`, `akvo-react-form-editor/README.md#setting-cascade-url`).

---

## 1. Embedded Cascade Data Objects

Cascading questions display parent-child filtered dropdowns. For static hierarchies, the cascade object is pre-defined on the form definition root (source: `akvo-react-form/README.md#cascade-any`):

```json
{
  "name": "Community Survey",
  "cascade": {
    "administration": [
      {
        "value": 1,
        "label": "Jawa Barat",
        "children": [
          { "value": 101, "label": "Garut" },
          { "value": 102, "label": "Bandung" }
        ]
      }
    ]
  }
}
```

---

## 2. Dynamic API Cascades (`api` Property)

Cascading select also supports chained API calls against SQLite / REST endpoints (source: `akvo-react-form/README.md#using-api-for-cascade`):

| Property | Type | Description |
|---|---|---|
| `endpoint` | String | API endpoint URL providing child cascade records. |
| `initial` | Integer \| String | Initial root parameter value (e.g. `0`). |
| `list` | String \| Boolean | Key name of data array in API response (`false` if response is a direct array). |

### Form Builder Setting (`settingCascadeURL` Prop)
In `WebformEditor`, the available cascade endpoints are passed via `settingCascadeURL` (source: `akvo-react-form-editor/README.md#setting-cascade-url`):
```jsx
<WebformEditor
  settingCascadeURL={[
    {
      id: 1,
      name: 'Province Cascade',
      endpoint: 'https://tech-consultancy.akvo.org/akvo-flow-web-api/cascade/seap/cascade-1.sqlite',
      initial: 0,
      list: false
    }
  ]}
/>
```

---

## 3. Entity Cascade Select (`entity`)

Entity select is a specialized cascading selector linked to external or tenant-registered master entities (e.g. schools, health facilities, water points) filtered by a parent administrative question (source: `akvo-react-form/README.md#entity`):

```json
{
  "id": 67,
  "name": "school_cascade",
  "label": "Select School Facility",
  "type": "cascade",
  "api": {
    "endpoint": "https://akvo.github.io/akvo-react-form/api/entities/1/"
  },
  "extra": {
    "type": "entity",
    "name": "School",
    "parentId": 5
  }
}
```
*(Source: `akvo-react-form/README.md#extra-entity`)*

---

## 4. Tree Hierarchies (`tree`)

Tree selector questions render expandable hierarchical nodes (source: `akvo-react-form/README.md#question`):
- `checkStrategy`: Controls what is stored in the selection box (`"parent"` shows parent node; `"children"` shows only leaf children).
- `expandAll`: Set `true` to auto-expand all tree nodes on load.
