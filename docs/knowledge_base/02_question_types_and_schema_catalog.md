# Question Types & Schema Attribute Catalog

This document is the exhaustive catalog of all 17 question types and their JSON schema attributes supported by the `akvo-react-form` runtime engine (source: `akvo-react-form/README.md#supported-field-type`, `akvo-react-form/README.md#question`).

---

## 1. Supported Field Types Catalog

| Type Key | Display Name | UI Configurable | Description & Common Use Cases |
|---|---|---|---|
| `input` | Text Input | Yes | Single-line text for names, codes, short answers (source: `akvo-react-form/README.md#supported-field-type`). |
| `number` | Number Input | Yes | Integer or decimal numbers for quantities, age, prices, metrics (source: `akvo-react-form/README.md#supported-field-type`). |
| `text` | TextArea / Memo | Yes | Multi-line text for long notes, descriptions, addresses (source: `akvo-react-form/README.md#supported-field-type`). |
| `option` | Single Choice | Yes | Radio buttons / single select list where exactly one choice is selected (source: `akvo-react-form/README.md#option`). |
| `multiple_option` | Multiple Choice | Yes | Checkboxes allowing multiple choices to be selected (source: `akvo-react-form/README.md#supported-field-type`). |
| `cascade` | Cascade Select | Yes | Hierarchical multi-level dropdowns (e.g. Province > District > Village) (source: `akvo-react-form/README.md#cascade-any`). |
| `date` | Date Picker | Yes | Calendar date picker for inspection dates, birth dates, timestamps (source: `akvo-react-form/README.md#supported-field-type`). |
| `geo` | Geopoint | Yes | Geographic point capturing Latitude, Longitude, Altitude, and Accuracy (source: `akvo-react-form/README.md#supported-field-type`). |
| `geotrace` | Geographic Polyline | Schema | Linear geographic coordinates for routes, pipelines, boundaries (source: `akvo-react-form/README.md#supported-field-type`). |
| `geoshape` | Geographic Polygon | Schema | Enclosed geographic area polygon for land parcels, fields (source: `akvo-react-form/README.md#supported-field-type`). |
| `photo` / `image` | Photo / Image | Yes | In-app camera photo capture or image file upload with max MB limits (source: `akvo-react-form/README.md#question`). |
| `signature` | Digital Signature | Yes | Hand-drawn touchscreen / mouse canvas signature pad (source: `akvo-react-form/README.md#supported-field-type`). |
| `attachment` | File Attachment | Yes | Generic file uploader for non-image files (PDF, spreadsheet, DOCX) (source: `akvo-react-form/README.md#supported-field-type`). |
| `autofield` | Computed Autofield | Yes | Dynamic read-only field calculated via mathematical function string (source: `akvo-react-form/README.md#autofieled-object`). |
| `tree` | Tree Hierarchy | Schema | Nested tree selector with parent/children check strategies (source: `akvo-react-form/README.md#question`). |
| `table` | Multiple Question Grid | Schema | Tabular multi-question grid with structured column definitions (source: `akvo-react-form/README.md#columns`). |
| `entity` | Entity Cascade Select | Schema | Cascade dropdown linked to tenant registered entity API endpoints (source: `akvo-react-form/README.md#entity`). |

---

## 2. Complete Question Schema Attribute Dictionary

Source: `akvo-react-form/README.md#question`

| Property | Type | Default | Description |
|---|---|---|---|
| `id` | Integer \| String | Required | Unique question identifier within the form definition. |
| `name` | String | Required | Internal variable name for database storage, exports, and formula references. |
| `type` | String | Required | One of the supported field types listed in Section 1 above. |
| `order` | Integer | `undefined` | Display position order of the question within its question group. |
| `tooltip` | String \| Object | `undefined` | Helper text or instructions displayed below the question prompt. |
| `required` | Boolean | `false` | When `true`, blocks submission until answered (ignored when hidden by skip logic). |
| `requiredSign` | String \| Component | `undefined` | Custom symbol or mark displayed next to the label when required is `true`. |
| `rule` | Object | `undefined` | Validation rules: `{ min: number, max: number, allowDecimal: boolean, allowedFileTypes: string[] }`. |
| `addonBefore` | String | `undefined` | Text or symbol prefix placed immediately before the input box (text and number only). |
| `addonAfter` | String | `undefined` | Text or symbol suffix placed immediately after the input box (text and number only). |
| `allowOther` | Boolean | `false` | Enables an "Other (please specify)" open-text choice for option questions. |
| `allowOtherText` | String | `undefined` | Custom label for the "Other" option choice. |
| `hiddenString` | Boolean | `false` | Masks input characters with dots and provides an eye toggle for passwords/PINs. |
| `requiredDoubleEntry` | Boolean | `false` | Prompts respondent to type value twice and validates exact match before submission. |
| `disabled` | Boolean | `false` | Renders the question in read-only state. |
| `displayOnly` | Boolean | `false` | Displays question text for respondent guidance but excludes it from submission payload. |
| `meta` | Boolean | `false` | Flags the question answer to be used as the summary name for the data point record. |
| `limit` | Integer | `undefined` | Maximum allowable file size limit in Megabytes (MB) for image/photo questions. |
| `fn` | Object | `undefined` | Autofield function configuration `{ fnString, multiline, fnColor }`. |
| `dependency` | Array | `undefined` | List of dependency condition objects for skip logic. |
| `dependency_rule` | String | `"AND"` | Logic evaluator for multiple dependencies: `"AND"` or `"OR"`. |
| `extra` | Array \| Object | `undefined` | HTML component blocks placed `before` or `after`, or entity cascade configuration. |
| `pre` | Object | `undefined` | Real-time cross-question copy rules on web forms for option choices. |
| `checkStrategy` | String | `"parent"` | Tree question selection display mode: `"parent"` or `"children"`. |
| `expandAll` | Boolean | `false` | Automatically expands all tree nodes by default when `true`. |
| `lead_repeat_group` | Array[Integer] | `undefined` | Binds a `multiple_option` question to lead multiple repeatable question groups. |
| `translations` | Array | `undefined` | Array of localized text objects `{ name, language }` for multi-language display. |
