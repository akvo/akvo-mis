# FAQ, Common Gotchas & Unsupported Features

This document provides quick answers to common questions and explicit boundaries of what Akvo MIS and `akvo-react-form` support versus do not support (source: `akvo-react-form/README.md`, `akvo-react-form-editor/README.md`, `docs/source/formBuilder.rst`).

---

## 1. Frequently Asked Questions & Edge Cases

### Q: Can I add icons or images inside question prefix/suffix (`addonBefore` / `addonAfter`)?

- **No**. Field prefixes and suffixes accept plain text strings and standard symbols only (e.g. `+62`, `$`, `kg`, `%`). Graphic icon classes, images, and HTML tags are not supported inside `addonBefore`/`addonAfter` (source: `akvo-react-form/README.md#question`).
- *Alternative*: Use the `extra.before` HTML content block in the form schema to render rich text, badges, or images above the question.

### Q: Is there a JSON viewer tab inside the Akvo MIS Form Builder?

- **No**. While the standalone demo has a JSON tab, Akvo MIS (`/control-center/form-builder/:formId/edit`) has **3 workspace tabs: `Edit Form`, `Translations`, `Preview`**. Raw JSON schema is exported via the **`Export JSON`** toolbar button (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx`).

### Q: Does setting a color code on an option choice change how data is stored or calculated?

- **No**. Hex color codes (`#28A745`, `#DC3545`) are purely visual aids rendered as colored badges/pills in the web form. They do not alter stored submission values or export columns (source: `akvo-react-form/README.md#option`).

### Q: Can monitoring forms auto-fill past registration answers on the web?

- **No**. Automatic pre-filling from registration to monitoring forms is an exclusive capability of the **Akvo MIS mobile app**. Web forms do not automatically pull past registration values into new forms.
- *Web same-session prefill*: Web forms only support copying an answer from Question A to Question B *within the same active form session* via the `pre` schema setting (source: `akvo-react-form/README.md#pre-filled-question`).

### Q: Why didn't skip logic copy over when I duplicated a question?

- Skip logic rules are intentionally **not copied** when clicking **"COPY QUESTION HERE"** to prevent circular or conflicting dependencies. Configure skip logic explicitly on the new question (source: `akvo-react-form-editor/README.md`).

### Q: What question types are supported in Akvo MIS?

- Exactly **13 question types** are supported in Akvo MIS (`frontend/src/lib/constants.js`): `input` (Text), `text` (TextArea/Memo), `number` (Number), `date` (Date), `image` (Photo/Image), `geo` (Geopoint), `option` (Single Choice), `multiple_option` (Multiple Choice), `cascade` (Cascade Select), `entity` (Entity Cascade), `autofield` (Calculated Autofield), `attachment` (File Attachment), and `signature` (Digital Signature).
- Types like `tree`, `table`, `geotrace`, and `geoshape` are restricted/unsupported in the standard Akvo MIS Form Builder.

### Q: How do I make a section repeatable in Form Builder?

- Click the Question Group header/settings icon, and toggle **`Repeatable`** to `true`. This allows respondents/enumerators to dynamically click `+ Add Row/Member` to enter multiple rows during data collection (source: `docs/knowledge_base/01_form_builder_editor_guide.md`).

### Q: How do I view previous versions or rollback a form?

- Click the **Version History** button (clock icon `HistoryOutlined`) in the top action toolbar above the Form Builder canvas. This opens the Version History Drawer on the right, listing all published version snapshots with dates, preview, and restore options (source: `frontend/src/pages/form-builder/FormBuilderEdit.jsx`).

### Q: How do I export or share my form definition?

- In the top action toolbar of the Form Builder Edit page, click **`Export JSON`** to download the raw JSON schema, **`Export XLSForm`** to download the Excel survey sheet, or **`Export Administration CSV`** for the cascade structure.

### Q: How do I mask sensitive PIN codes or passwords on screen?

- In the question settings modal for an `input` (text) question, enable the **Mask / Password (`hiddenString`)** toggle. This displays dots instead of text as the user types, with an eye toggle to show/hide (source: `docs/knowledge_base/06_advanced_properties_and_modifiers.md`). It is a setting modifier on `input`, not a separate question type.

### Q: How do I enable double entry verification to prevent typos?

- In the question settings modal for an `input` or `number` question, enable the **Double Entry (`requiredDoubleEntry`)** toggle. This requires the user to enter the same value twice and blocks form submission until both entries match (source: `docs/knowledge_base/06_advanced_properties_and_modifiers.md`).

### Q: Can I create Matrix / Table questions in the visual Form Builder drag-and-drop UI?

- Table / Matrix questions are defined in the **raw form JSON schema** and cannot be constructed via drag-and-drop in the visual UI (source: `akvo-react-form/README.md#columns`).

### Q: What operator is used to combine multiple skip logic rules?

- The `dependency_rule` property controls multiple rules: `"AND"` (default: all must be true) or `"OR"` (at least one must be true) (source: `akvo-react-form/README.md#dependency-rule-logic`).
