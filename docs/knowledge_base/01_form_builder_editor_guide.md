# Akvo MIS Form Builder Editor Guide

This document is the technical reference for the **Form Builder Edit Page** within the Akvo MIS platform, located at `http://localhost:3000/control-center/form-builder/:formId/edit` (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx`).

---

## 1. Page Layout & Navigation

When opening a form to edit in Akvo MIS (**Control Centre > Form Builder > [Select Form] > Edit**), the page contains three distinct sections:
- **Top Header & Breadcrumbs**: Displays navigation path `Control Centre > Form Builder > Edit Form`.
- **Action Toolbar**: Action buttons for file exports, version management, and lifecycle state changes.
- **Embedded Webform Editor**: The core `WebformEditor` component workspace from `akvo-react-form-editor`.

---

## 2. Top Action Toolbar Buttons

Located in the header above the editor canvas (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx#L344-L421`):

| Button | Icon / Type | Action & Purpose in Akvo MIS |
|---|---|---|
| **Export JSON** | Download | Downloads the raw JSON form schema file (`.json`) representing the current form definition. |
| **Export XLSForm** | Download | Exports an XLSForm-compatible Excel file (`.xlsx`) containing `survey`, `choices`, and `settings` sheets. |
| **Export Administration CSV** | Download | Exports the tenant administrative cascade hierarchy linked to this form. |
| **Version History** | Clock (`HistoryOutlined`) | Opens the **Version History Drawer** on the right side of the screen. Displays all immutable published snapshot versions with timestamps and preview/restore actions. |
| **Publish** | Primary Blue | Publishes the current draft live. Enumerators and web respondents can immediately collect data against this new version. |
| **Unpublish** | Popconfirm | Reverts the form from published status back to draft status, pausing live data collection. |

---

## 3. The Three Workspace Tabs in Akvo MIS

Inside the Form Builder workspace, `WebformEditor` renders **3 primary tabs** (source: `akvo-react-form-editor/dist/index.modern.js`, `frontend/src/pages/form-builder/FormBuilderEdit.jsx`):

### Tab 1: Edit Form (Default Workspace)
- **Purpose**: Main visual drag-and-drop workspace for structuring sections and question cards.
- **Question Groups**: Sections grouping related questions (see Section 4 below).
- **Group Actions**: Click **+ Add Group** at the bottom to append a new section.
- **Question Actions**: Click **+ Add Question** inside a group to insert a question card.
- **Duplicate Question**: Click **COPY QUESTION HERE** below any question to duplicate label, type, options, and settings. Note: Skip logic is **NOT** copied to prevent circular dependencies (source: `akvo-react-form-editor/README.md`).
- **Question Settings Modal**: Clicking any question opens its settings panel with sub-tabs:
  - **`Setting`**: Label, Variable Name, Tooltip, Required, Min/Max bounds, Double Entry, Password Mask, Prefix (`addonBefore`), Suffix (`addonAfter`), and Option Hex Colors.
  - **`Skip Logic`**: Conditional dependency configuration rules.

### Tab 2: Translations
- **Purpose**: Multi-language localization workspace for multilingual surveys (source: `akvo-react-form-editor/README.md#translations`).
- **Language Selector**: Choose the target language code from the dropdown (e.g. `id`, `fr`, `es`).
- **Translation Grid**: Side-by-side editing of question prompts, tooltips, option choice labels, and group headers.
- **Fallback**: Untranslated fields automatically fall back to the base language.

#### Translation Object Schema
Source: `akvo-react-form/README.md#translations-optional`

| Property | Type | Description |
|---|---|---|
| `Unique{any}` | Object / String | Target property to be translated (e.g. `name`, `label`, `description`, `content`). |
| `language` | Enum[ISO 639-1] | Language code for the translation (e.g. `"id"`, `"fr"`, `"es"`). |

### Tab 3: Preview
- **Purpose**: Live, interactive runtime preview of the form as field respondents and enumerators will experience it (source: `akvo-react-form-editor/README.md#preview`).
- **Verification**: Used to test skip logic visibility, autofield mathematical calculations, required field triggers, and repeatable group entry rows prior to publishing.

---

## 4. Question Group Properties Dictionary

Source: `akvo-react-form/README.md#question-group`

| Property | Type | Default | Description |
|---|---|---|---|
| `id` | Integer | Required | Unique identifier for the question group. |
| `name` | String | Required | Title / heading displayed for the question group section. |
| `order` | Integer | `undefined` | Sequence order of the group in the form. |
| `description` | String | `undefined` | Narrative description or instructions displayed under the group header. |
| `repeatable` | Boolean | `false` | Enables repeating rows/rosters for collecting tabular multi-row data. |
| `leading_question` | Integer \| String | `undefined` | Designates a specific question ID as the repeating row leader. |
| `show_repeat_in_question_level` | Boolean | `false` | Renders repeatable rows at question level rather than boxed group format. |
| `question` | Array[Question] | Required | Array of child question objects belonging to this group. |
| `translations` | Array[Translations] | `undefined` | Array of localized group titles and descriptions. |

---

## 5. Platform Distinction: No In-Page JSON Tab in Akvo MIS

In the standalone `akvo-react-form-editor` library demo website, an extra "JSON" tab is shown for developer testing. However, **in the Akvo MIS platform, there is NO in-page JSON tab / viewer**.
- To inspect or obtain the form's raw JSON schema in Akvo MIS, click the **`Export JSON`** button in the top action toolbar (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx#L355-L362`).

---

## 6. Version History Drawer & Banners

- **Information Banners (`FormEditorBanners`)**: Renders status banners above the editor canvas:
  - *Published Info Banner*: Indicates the form is currently live and receiving submissions.
  - *Pending Snapshot Banner*: Indicates changes have been saved to a published form and are ready to be published as the next version (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx#L324-L332`).
  - *Version Preview Banner*: Renders when inspecting an older read-only snapshot, with an **"Exit Preview"** button.
- **Version History Drawer (`VersionHistoryDrawer`)**:
  - Displays chronological list of published version snapshots (e.g. Version 1, Version 2).
  - Provides **Preview** (read-only inspection) and **Restore / Activate** actions (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx#L441-L460`).

---

## 7. Importing Forms & Interoperability (KoboToolbox, ODK & XLSForm)

Source: `frontend/src/pages/form-builder/FormBuilderList.jsx`, `frontend/src/pages/form-builder/components/ImportFormModal.jsx`, `docs/source/formBuilder.rst`

Akvo MIS provides native tools for moving forms into and out of the platform:

### 1. Import Form Modal (`/control-center/form-builder`)
On the Form Builder List page, click the **Import Form** button in the header toolbar to open the `ImportFormModal`. Two import formats are supported:
1. **JSON (`.json`)**: Imports a complete Akvo MIS form schema previously exported from another Akvo MIS tenant or deployment.
2. **XLSForm (`.xlsx` / `.xls`)**: Imports standard spreadsheet questionnaires authored externally in tools like **KoboToolbox**, **ODK Build**, or Microsoft Excel.

### 2. Working with Forms from KoboToolbox or ODK
- **Direct Web Builder Embed**: **Not supported**. You cannot directly embed or run Kobo's web builder inside Akvo MIS.
- **XLSForm Transition Path**: **Fully supported**. If you created a form in KoboToolbox or ODK:
  1. In KoboToolbox / ODK, export your form definition as an **XLSForm (`.xlsx`)**.
  2. In Akvo MIS, go to **Control Centre > Form Builder** and click **Import Form**.
  3. Select **XLSForm (.xlsx)**, choose whether the form is a **Registration** or **Monitoring** form, and upload the `.xlsx` file.
  4. Akvo MIS runs preflight checks to validate question types, choices, skip-logic dependencies, and multi-language translations (`label::*`), then creates a native draft form in the Form Builder.
  5. Open the form in the Form Builder to review question layout and publish when ready.

