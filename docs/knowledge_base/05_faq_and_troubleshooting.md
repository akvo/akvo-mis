# FAQ, Common Gotchas & Unsupported Features

This document provides quick answers to frequent questions, common pitfalls, and explicit boundaries of what Akvo MIS supports versus does not support.

---

## Frequently Asked Questions

### Q: Can I put icons or images inside question prefix/suffix (`addonBefore` / `addonAfter`)?
- **No**. Prefix and suffix fields only support plain text and standard symbols (e.g. `+62`, `$`, `kg`, `cm`, `%`). Images, icons, or HTML tags are not supported inside addonBefore.
- *Alternative*: If you need to display an explanatory image or banner, use the `extra.before` HTML block in the form schema.

### Q: Does setting a color code on an option choice change how data is exported or calculated?
- **No**. Hex color codes (`#28A745`, `#DC3545`, etc.) are purely visual tags to help respondents and reviewers identify statuses quickly in web forms. Data is exported as standard choice values.

### Q: Can monitoring forms auto-fill past registration answers on the web?
- **No**. Automatic pre-filling from registration to monitoring forms is an exclusive capability of the **Akvo MIS mobile app**. Web forms do not automatically pull past registration values into new forms.
- *Web same-session prefill*: Web forms only support copying an answer from Question A to Question B *within the same active form session* via the `pre` schema setting.

### Q: Why isn't my skip logic working?
- Check the following common causes:
  1. **Configured on the Wrong Question**: Make sure skip logic is added on the **dependent question** (the one being hidden/shown), not on the trigger question.
  2. **Question Order**: The trigger question must appear *before* the dependent question in the form layout.
  3. **Case Sensitivity & Exact Values**: For `Equal` logic on Option fields, ensure the trigger value matches the option `value` code (not necessarily the display label).
  4. **Circular Dependencies**: Ensure Question A does not depend on B while B depends on A.

### Q: When I copy a question, why are the skip logic rules missing?
- Skip logic is intentionally **not copied** when duplicating a question using "COPY QUESTION HERE". This prevents conflicting dependencies. You must set up skip logic rules explicitly on the new question.
- Always remember to update the variable name of the duplicated question so it remains unique.

### Q: Can I create Matrix / Table questions in the visual Form Builder UI?
- Table / Matrix questions are defined in the **raw form JSON schema** (via the JSON tab) and cannot be constructed via drag-and-drop in the visual UI.

### Q: How do I test my form before publishing?
- Always click the **Preview Tab** at the top of the Form Builder editor. This opens an interactive simulation where you can test skip logic, validations, autofield formulas, and repeatable groups before publishing live to enumerators.
