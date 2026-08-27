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

### Q: Can I create Matrix / Table questions in the visual Form Builder drag-and-drop UI?
- Table / Matrix questions are defined in the **raw form JSON schema** and cannot be constructed via drag-and-drop in the visual UI (source: `akvo-react-form/README.md#columns`).

### Q: What operator is used to combine multiple skip logic rules?
- The `dependency_rule` property controls multiple rules: `"AND"` (default: all must be true) or `"OR"` (at least one must be true) (source: `akvo-react-form/README.md#dependency-rule-logic`).
