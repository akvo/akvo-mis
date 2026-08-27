# Akvo MIS Form Builder Edit Page Reference (`/control-center/form-builder/:formId/edit`)

This document is the definitive guide to the **Form Builder Edit Page** in Akvo MIS, located at `http://localhost:3000/control-center/form-builder/:formId/edit` (`frontend/src/pages/form-builder/FormBuilderEdit.jsx`).

---

## 1. Page Layout & Structure in Akvo MIS

When navigating to `Control Centre > Form Builder > [Select a Form] > Edit`, the page layout is structured as follows:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Breadcrumbs: Control Centre > Form Builder > Edit Form                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Action Toolbar: [ Export JSON ] [ Export XLSForm ] [ Export Admin CSV ]      │
│                 [ 🕒 Version History ] [ Publish ] [ Unpublish ]             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Banners: Form Published Info / Pending Snapshot Banner / Version Preview     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Embedded Webform Editor:                                                     │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Tabs: [ Edit Form ]    [ Translations ]    [ Preview ]                   │ │
│ ├──────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                          │ │
│ │ (Active Tab Workspace: Question Groups, Question Cards, Settings Modal)  │ │
│ │                                                                          │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **Important Platform Note (Akvo MIS vs. Standalone Library Demo)**:
> In the standalone `akvo-react-form-editor` developer demo website, an extra "JSON" tab is shown for demo purposes. However, **in the Akvo MIS platform, there is NO in-page JSON tab / viewer**.
> - To inspect or obtain the form's raw JSON schema in Akvo MIS, use the **`Export JSON`** button in the top action toolbar.

---

## 2. Top Action Toolbar Buttons

Located in the top-right header above the editor canvas:

| Button | Icon | Action / Purpose in Akvo MIS |
|---|---|---|
| **Export JSON** | Download | Downloads the raw JSON schema file for the current form definition (`.json`). |
| **Export XLSForm** | Download | Generates and downloads an XLSForm-compatible Excel spreadsheet (`.xlsx`) containing `survey`, `choices`, and `settings` sheets. |
| **Export Administration CSV** | Download | Exports the tenant administrative cascade hierarchy linked to this form. |
| **Version History** | Clock (`HistoryOutlined`) | Opens the **Version History Drawer** on the right side of the screen. Shows all published snapshot versions, timestamps, and allows previewing or restoring an older version. |
| **Publish** | Primary Blue | Publishes the current draft changes live. Creates a new immutable version snapshot in the Version History. |
| **Unpublish** | Popconfirm | Reverts the form from published status back to draft status, pausing live data collection. |

---

## 3. The 3 Editor Workspace Tabs in Akvo MIS

Inside the Form Builder workspace, there are **3 primary tabs**:

### Tab 1: Edit Form (Default Workspace)
- **What it is**: The main visual drag-and-drop builder for organizing sections and question elements.
- **Controls & Actions**:
  - **Question Groups**: Sections that group related questions. Each group has a title, collapse/expand toggle, drag handle to reorder, and a **Repeatable** toggle (for rosters/sub-tables).
  - **+ Add Group**: Adds a new group section to the bottom of the form.
  - **+ Add Question**: Adds a new question card into the active question group.
  - **COPY QUESTION HERE**: Appears below each question card to duplicate the question (duplicates type, label, and options; does **not** copy skip logic).
  - **Settings Panel**: Clicking any question opens its settings drawer/modal with sub-tabs:
    - **`Setting`**: Label, Variable Name, Tooltip, Required, Min/Max validation, Double Entry, Mask/Password, Prefix (`addonBefore`), Suffix (`addonAfter`), and Option Hex Colors.
    - **`Skip Logic`**: Dependent logic operator rules (`=`, `!=`, `contains`, `>`, `<`, `between`).

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
