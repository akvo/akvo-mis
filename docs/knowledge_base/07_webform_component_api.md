# Webform & WebformEditor Component API

This document details the React component props for `Webform` (runtime) and `WebformEditor` (builder) (source: `akvo-react-form/README.md#webform`, `akvo-react-form-editor/README.md#webformeditor`).

---

## 1. `Webform` Component Props (`akvo-react-form`)

Source: `akvo-react-form/README.md#webform`

| Prop Name | Type | Default | Description |
|---|---|---|---|
| `forms` | Object | Required | Root form definition JSON object. |
| `sidebar` | Boolean | `true` | Option to show or hide the question group sidebar. |
| `sticky` | Boolean | `false` | Sticky positioning for header and sidebar navigation. |
| `onFinish` | Function | - | Callback triggered after form submission with valid values: `function(values, refreshForm)`. |
| `onChange` | Function | - | Triggered after any field change: `function({ current, values, progress })`. |
| `onCompleteFailed` | Function | - | Triggered when submit is clicked with blank required fields: `function(values, errorFields)`. |
| `initialValue` | Array | `[]` | Array of initial value objects `{ question: id, value: val, repeatIndex: 0 }`. |
| `autoSave` | Object | `undefined` | Enables automatic draft saving into IndexedDB `{ formId, name, buttonText }`. |
| `printConfig` | Object | `undefined` | Enables printable survey layout `{ showButton, filename, hideInputType, header }`. |
| `downloadSubmissionConfig` | Object | `undefined` | Enables direct Excel submission download `{ visible, filename, horizontal }`. |
| `languagesDropdownSetting` | Object | `{}` | Controls the active language switcher `{ showLanguageDropdown, languageDropdownValue }`. |
| `UIText` | Object | `{}` | Localization dictionary overrides mapped by ISO 639-1 language code. |

---

## 2. `WebformEditor` Component Props (`akvo-react-form-editor`)

Source: `akvo-react-form-editor/README.md#webformeditor`

| Prop Name | Type | Description |
|---|---|---|
| `initialValue` | Object | Form definition object to initialize the editor canvas with (source: `akvo-react-form-editor/README.md#initial-value-optional`). |
| `onSave` | Function | Callback triggered when saving changes: `function(values)`. |
| `limitQuestionType` | Array[String] | Limits the allowable question types in the question palette. |
| `defaultQuestion` | Object | Custom defaults for newly added questions: `{ type, name, required }`. |
| `settingCascadeURL` | Array[Object] | Configures cascade endpoint definitions `{ id, name, endpoint, initial, list }`. |
| `settingHintURL` | Object | Configures hint / data API validation sources. |
| `customParams` | Object | Injects custom key-value parameter settings into the editor (source: `akvo-react-form-editor/README.md#custom-params`). |

---

## 3. Custom Parameters Configuration (`customParams`)

Custom parameters allow injecting custom tenant metadata tabs into the editor (source: `akvo-react-form-editor/README.md#custom-params`):

```jsx
<WebformEditor
  customParams={{
    label: 'Custom Parameters',
    params: [
      {
        name: 'param_category',
        label: 'Category',
        type: 'option',
        multiple: false,
        options: [
          { label: 'Primary', value: 'P1' },
          { label: 'Secondary', value: 'S2' }
        ]
      },
      {
        name: 'param_notes',
        label: 'Internal Notes',
        type: 'input'
      }
    ]
  }}
/>
```
*(Source: `akvo-react-form-editor/README.md#custom-params`)*
