# Akvo MIS Form Builder Edit Page Reference (`/control-center/form-builder/:formId/edit`)

This document is the definitive guide to the **Form Builder Edit Page** in Akvo MIS, located at `http://localhost:3000/control-center/form-builder/:formId/edit` (`frontend/src/pages/form-builder/FormBuilderEdit.jsx`).

---

## 1. Page Layout & Structure

When navigating to `Control Centre > Form Builder > [Select a Form] > Edit`, the page is structured into three main sections:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Breadcrumbs: Control Centre > Form Builder > Edit Form                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Action Toolbar: [ Export JSON ] [ Export XLSForm ] [ Export Admin CSV ]      │
│                 [ 🕒 Version History ] [ Publish ] [ Unpublish ]             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Banners: Form Published Info / Pending Snapshot Banner / Version Preview     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Embedded Webform Editor (akvo-react-form-editor):                            │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Tabs: [ Edit Form ]    [ Translations ]    [ Preview ]    [ JSON ]       │ │
│ ├──────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                          │ │
│ │ (Active Tab Workspace: Question Groups, Question Cards, Settings Panel)  │ │
│ │                                                                          │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Top Action Toolbar Buttons

Located in the top-right header above the editor canvas:

| Button | Icon | Action / Purpose |
|---|---|---|
| **Export JSON** | Download | Downloads the raw JSON schema file for the current form definition (`.json`). |
| **Export XLSForm** | Download | Generates and downloads an XLSForm-compatible Excel spreadsheet (`.xlsx`) containing `survey`, `choices`, and `settings` sheets. |
| **Export Administration CSV** | Download | Exports the tenant administrative cascade hierarchy linked to this form. |
| **Version History** | Clock (`HistoryOutlined`) | Opens the **Version History Drawer** on the right side of the screen. Shows all published snapshot versions, timestamps, and allows previewing or restoring an older version. |
| **Publish** | Primary Blue | Publishes the current draft changes live. Creates a new immutable version snapshot in the Version History. |
| **Unpublish** | Popconfirm | Reverts the form from published status back to draft status, pausing live data collection. |

---

## 3. The 4 Editor Workspace Tabs (`akvo-react-form-editor`)

Inside the main editor panel, `WebformEditor` provides four workspace tabs:

### Tab 1: Edit Form (Default Workspace)
- **What it is**: The visual drag-and-drop builder for organizing sections and question elements.
- **Controls & Actions**:
  - **Question Groups**: Sections that group related questions. Each group has a title, collapse/expand toggle, drag handle to reorder, and a **Repeatable** toggle (for rosters/sub-tables).
  - **+ Add Group**: Adds a new group section to the bottom of the form.
  - **+ Add Question**: Adds a new question card into the active question group.
  - **COPY QUESTION HERE**: Appears below each question card to duplicate the question (duplicates type, label, and options; does **not** copy skip logic).
  - **Settings Panel**: Clicking any question opens its sidebar to configure Label, Variable Name, Tooltip, Required, Min/Max validation, Double Entry, Mask/Password, Prefix (`addonBefore`), Suffix (`addonAfter`), Option Hex Colors, and Skip Logic rules.

### Tab 2: Translations
- **What it is**: The multi-language localization workspace.
- **Controls & Actions**:
  - **Language Selector**: Choose the target language from the dropdown menu (e.g. Indonesian, French, Spanish, Swahili).
  - **Side-by-Side Translation Grid**: Enter translated text for question prompts, tooltips, option choice labels, and group headers.
  - **Fallback**: Untranslated fields automatically fall back to the base language.

### Tab 3: Preview
- **What it is**: A live, interactive runtime preview of the form as field respondents and enumerators will experience it.
- **Recommended Usage**: Always test here before clicking **Publish**:
  - Verify that **Skip Logic** reveals and hides dependent questions as expected.
  - Test **Autofield calculations** with sample numeric inputs.
  - Check **Double Entry** and **Required** validation prompts.
  - Test **Repeatable Question Groups** by adding and removing rows.

### Tab 4: JSON
- **What it is**: The raw form definition schema viewer and editor.
- **Controls & Actions**:
  - View and edit the complete underlying JSON schema.
  - Used for advanced configurations not exposed in the visual drag-and-drop palette (e.g., Table / Matrix questions, `extra.before`/`extra.after` HTML content blocks, and same-session `pre` cross-question copy rules).

---

## 4. Status Banners & Version History Drawer

### Information Banners (`FormEditorBanners`)
- **Published Info Banner**: Appears when the form is active and receiving live submissions.
- **Pending Snapshot Banner**: Appears when changes have been made to a published form, indicating that a new draft is ready to be published as the next version.
- **Version Preview Banner**: Appears when viewing an older read-only snapshot from the Version History drawer, with an **"Exit Preview"** button to return to the active draft.

### Version History Drawer (`VersionHistoryDrawer`)
- Lists all historical published versions in chronological order.
- Each version card displays:
  - Version number (e.g. Version 1, Version 2)
  - Date and time published
  - **Preview Button**: Loads the historical form state into the editor in read-only mode.
  - **Restore / Activate Button**: Reverts the active form definition to that specific historical snapshot.
