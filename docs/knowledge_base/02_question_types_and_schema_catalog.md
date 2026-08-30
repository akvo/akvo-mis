# Question Types & Schema Attribute Catalog

This document is the exhaustive catalog of all 17 question types and their JSON schema attributes supported by the `akvo-react-form` runtime engine (source: `akvo-react-form/README.md#supported-field-type`, `akvo-react-form/README.md#question`).

---

## 1. Supported Field Types in Akvo MIS (`frontend/src/lib/constants.js`)

In the Akvo MIS platform (`QUESTION_TYPES` constant in `frontend/src/lib/constants.js`), exactly **13 question types** are supported and active in the Form Builder:

| Type Key | Display Name in Akvo MIS | Description & Purpose |
|---|---|---|
| `input` | Text Input | Single-line text for names, codes, short text (source: `frontend/src/lib/constants.js`). |
| `text` | TextArea / Long Memo | Multi-line text for long notes, descriptions, narratives (source: `frontend/src/lib/constants.js`). |
| `number` | Number Input | Numerical input for quantities, age, prices, metrics (source: `frontend/src/lib/constants.js`). |
| `date` | Date Picker | Calendar date selection for inspections, birthdays, events (source: `frontend/src/lib/constants.js`). |
| `image` | Photo / Image | Camera photo capture and image upload (source: `frontend/src/lib/constants.js`). |
| `geo` | Geopoint | GPS coordinates (Latitude, Longitude, Altitude, Accuracy) (source: `frontend/src/lib/constants.js`). |
| `option` | Single Choice | Radio buttons / single select list where exactly one choice is chosen (source: `frontend/src/lib/constants.js`). |
| `multiple_option` | Multiple Choice | Checkboxes allowing multiple choices to be selected (source: `frontend/src/lib/constants.js`). |
| `cascade` | Cascade Select | Hierarchical multi-level dropdowns (e.g. Province > District > Village) (source: `frontend/src/lib/constants.js`). |
| `entity` | Entity Cascade | Cascade dropdown linked to tenant master entities (source: `frontend/src/lib/constants.js`). |
| `autofield` | Calculated Autofield | Dynamic read-only calculation evaluated via JavaScript function string (source: `frontend/src/lib/constants.js`). |
| `attachment` | File Attachment | File uploader for non-image files (PDF, spreadsheet, DOCX) (source: `frontend/src/lib/constants.js`). |
| `signature` | Digital Signature | Touchscreen / mouse hand-drawn canvas signature pad (source: `frontend/src/lib/constants.js`). |

> **Restricted / Unsupported Types in Akvo MIS**:
> Although underlying libraries (`akvo-react-form`) define `tree`, `table`, `geotrace`, and `geoshape`, these types are **restricted and not enabled** in the standard Akvo MIS Form Builder palette (`frontend/src/lib/constants.js`).

---

## 2. Core Form Engine Feature Set

Source: `akvo-react-form/README.md#feature-set`

| Feature | Description |
|---|---|
| Initial values | Predefine default values for form fields to streamline user input. |
| Question Group Description | Provides a description for a group of related questions in the form. |
| Translations | Enables multilingual support by allowing form fields and labels to be displayed in multiple languages. |
| Multiple Question Dependency | Allows questions to depend on multiple other questions, enabling complex conditional logic. |
| Rule based response validation | Validates user responses based on predefined rules, such as minimum and maximum values. |
| Save Datapoint | Allows users to save form responses as a draft for later completion or review. |
| Computed field value | Automatically calculates and displays a value based on other field inputs. |
| Clear response | Allows users to reset or clear their responses for specific fields or the entire form. |
| Custom style | Allows users to apply custom CSS styles to form elements for a tailored appearance. |
| Tooltip | Provides additional information or guidance to users when they hover over a form element. |
| Extra component on Question | Allows users to add custom components before or after a question for enhanced functionality or additional context. |
| HTML Support on Question | Allows embedding and rendering of HTML content within form questions for enhanced customization. |
| Field Suffix / Prefix | Allows users to add custom text or symbols before or after input fields for better context or formatting. |
| Print | Allows users to print the form or its responses for offline use or record-keeping. |
| Download response to tabular format | Allows users to export form responses into a structured tabular format, such as CSV or Excel. |
| Upload any file type attachment | Allows users to upload files of any format as attachments. |

---

## 3. Root Form Schema Structure

Source: `akvo-react-form/README.md#form-root`

| Property | Type | Description |
|---|---|---|
| `name` | String | Form title / name. |
| `question_group` | Array[QuestionGroup] | List of question group sections in sequential order. |
| `Unique{any}` | Object | Cascade definition, can be any named property (e.g. `cascade: { administration: [...] }`). |
| `languages` | Array[String] | List of available ISO 639-1 language codes (e.g. `["en", "id", "fr"]`). |
| `defaultLanguage` | String | Default active language code. |
| `translations` | Array[Translations] | Array of localized form title translations `[{"name": "...", "language": "id"}]`. |

---

## 4. Complete Question Schema Attribute Dictionary

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
| `partialRequired` | Boolean | `false` | Custom rule for cascade fields allowing completion without selecting leaf nodes. |
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
| `dataApiUrl` | String | `undefined` | API data endpoint returning pair of object and value for dynamic validation. |
| `dependency` | Array | `undefined` | List of dependency condition objects for skip logic. |
| `dependency_rule` | String | `"AND"` | Logic evaluator for multiple dependencies: `"AND"` or `"OR"`. |
| `extra` | Array \| Object | `undefined` | HTML component blocks placed `before` or `after`, or entity cascade configuration. |
| `pre` | Object | `undefined` | Real-time cross-question copy rules on web forms for option choices. |
| `checkStrategy` | String | `"parent"` | Tree question selection display mode: `"parent"` or `"children"`. |
| `expandAll` | Boolean | `false` | Automatically expands all tree nodes by default when `true`. |
| `lead_repeat_group` | Array[Integer] | `undefined` | Binds a `multiple_option` question to lead multiple repeatable question groups. |
| `translations` | Array | `undefined` | Array of localized text objects `{ name, language }` for multi-language display. |

---

## 5. Option Object Properties (`option`)

Source: `akvo-react-form/README.md#option`

| Property | Type | Description |
|---|---|---|
| `name` | String | Option display label and stored value. |
| `order` | Integer | Display sequence order. |
| `color` | String | Hex color string (e.g. `"#28A745"`) for visual badge rendering on web forms. |
| `translations` | Array[Translations] | Array of localized option translations. |

---

## 6. Columns Object Properties (`table`)

Source: `akvo-react-form/README.md#columns`

| Property | Type | Description |
|---|---|---|
| `name` | String | Column / sub-question variable key. |
| `type` | String | Column input type: `number`, `input`, `text`, or `option`. |
| `label` | String | Header label displayed for the column. |
| `option` | Array[Option] | List of options when column `type` is `option`. |
