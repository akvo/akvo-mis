# Webform & WebformEditor Component API

This document details the React component props for `Webform` (runtime engine) and `WebformEditor` (form builder) (source: `akvo-react-form/README.md#webform`, `akvo-react-form-editor/README.md#webformeditor`).

---

## 1. `Webform` Component Props (`akvo-react-form`)

Source: `akvo-react-form/README.md#webform`

| Prop Name | Type | Default | Description |
|---|---|---|---|
| `forms` | Object | Required | Root form definition JSON object containing `question_group`, `cascade`, and `languages`. |
| `sidebar` | Boolean | `true` | Option to show or hide the question group navigation sidebar. |
| `sticky` | Boolean | `false` | Sticky positioning for header and sidebar navigation on scrolling. |
| `onFinish` | Function | - | Callback triggered after form submission and validation: `function(values, refreshForm)`. |
| `onChange` | Function | - | Triggered after any field change: `function({ current, values, progress })`. |
| `onCompleteFailed` | Function | - | Triggered when submit is clicked with blank required fields: `function(values, errorFields)`. |
| `submitButtonSetting` | Object | `{}` | Submit button state configuration: `{ loading: boolean, disabled: boolean }`. |
| `extraButton` | ReactComponent | `undefined` | Custom React component button rendered alongside the Submit button. |
| `initialValue` | Array | `[]` | Predefined values array: `[{ question: id, value: val, repeatIndex: 0 }]`. |
| `autoSave` | Object | `undefined` | Enables automatic draft saving to browser IndexedDB `{ formId, name, buttonText }`. |
| `printConfig` | Object | `undefined` | Enables printable survey layout `{ showButton, filename, hideInputType, header }`. |
| `downloadSubmissionConfig` | Object | `undefined` | Enables direct Excel submission download `{ visible, filename, horizontal }`. |
| `leftDrawerConfig` | Object | `undefined` | Renders a sliding left drawer `{ visible, title, Content }`. |
| `fieldIcons` | Boolean | `true` | Controls whether field type icons are displayed next to input and number fields. |
| `formRef` | React useRef | `null` | Passes a React `useRef` to control form state from the host component. |
| `showSpinner` | Boolean | `false` | Displays a loading spinner when data seeding is in progress. |
| `languagesDropdownSetting` | Object | `{}` | Controls the language switcher `{ showLanguageDropdown, languageDropdownValue }`. |
| `UIText` | Object | `{}` | Custom UI localization overrides mapped by ISO 639-1 language code. |

---

## 2. Draft Storage & Auto-Save API (`autoSave` & `dataStore`)

When `autoSave` is enabled, the runtime saves form state to browser IndexedDB (source: `akvo-react-form/README.md#auto-save-object`).

- **`autoSave` Configuration**:
```json
{
  "formId": 101,
  "name": "Household Survey Draft",
  "buttonText": "Save Draft"
}
```
- **`dataStore` Helper Methods**:
  - `dataStore.list(formId)`: Returns a Promise resolving to all saved datapoint drafts for `formId`.
  - `datapoint.load()`: Restores draft values into the active form.
  - `datapoint.remove()`: Deletes the draft from local storage.

---

## 3. Initial Value Format (`initialValue`)

Pre-populates values upon form initialization (source: `akvo-react-form/README.md#initial-value-optional`):

| Property | Type | Description |
|---|---|---|
| `question` | Integer \| String | Question ID to populate. |
| `value` | String \| Number \| Object \| Array | Value (e.g. text string, numeric value, `{lat, lng}`, or selected option IDs). |
| `repeatIndex` | Integer | Target row index within a repeatable question group (default: `0`). |

---

## 4. `WebformEditor` Component Props (`akvo-react-form-editor`)

Source: `akvo-react-form-editor/README.md#webformeditor`

| Prop Name | Type | Description |
|---|---|---|
| `initialValue` | Object | Form definition object to initialize the editor canvas with (source: `akvo-react-form-editor/README.md#initial-value-optional`). |
| `onSave` | Function | Callback triggered when user saves form changes: `function(values)`. |
| `limitQuestionType` | Array[String] | Array of allowable question types to restrict the builder palette. |
| `defaultQuestion` | Object | Custom defaults for newly added questions: `{ type, name, required }`. |
| `settingCascadeURL` | Array[Object] | Configures available cascade endpoint sources `{ id, name, endpoint, initial, list }`. |
| `settingHintURL` | Object | Configures dynamic hint and data API validation endpoints. |
| `customParams` | Object | Configures custom key-value parameter tabs in question settings. |

---

## 5. Setting Hint URL (`settingHintURL`)

Used to provide remote validation or reference data hints for numeric fields (source: `akvo-react-form-editor/README.md#setting-hint-url`):

| Property | Type | Description |
|---|---|---|
| `questionTypes` | Array[String] | Limits hint setting to specific question types (e.g. `["number"]`). |
| `settings` | Array[Object] | Array of hint endpoints `{ id, name, endpoint, path: [{ label, value }] }`. |

---

## 6. Custom Parameters (`customParams`)

Injects custom metadata tabs into question settings (source: `akvo-react-form-editor/README.md#custom-params`):

| Property | Type | Description |
|---|---|---|
| `label` | String | Label for the custom parameters tab in question settings. |
| `params` | Array[Object] | List of custom parameter definitions `{ name, label, type, multiple, options }`. |
