# Advanced Field Properties, Modifiers & Validation Rules

This document details specialized properties, modifiers, and validation rules in `akvo-react-form` (source: `akvo-react-form/README.md#question`, `akvo-react-form/README.md#rule`, `akvo-react-form/README.md#extra-component`, `akvo-react-form/README.md#pre-filled-question`).

---

## 1. Input Adornments: Prefix & Suffix

- **Supported Types**: `input` (text) and `number` fields only (source: `akvo-react-form/README.md#question`).
- **`addonBefore`**: String or text symbol rendered immediately before the input box (e.g. `+62`, `$`, `ID:`).
- **`addonAfter`**: String or text symbol rendered immediately after the input box (e.g. `kg`, `cm`, `%`, `USD`).
- **Constraint**: Plain text strings and standard symbols only. Graphic icons, images, or CSS icon classes are **not** supported inside addonBefore/addonAfter.

---

## 2. Security & Verification Modifiers

- **Password Masking (`hiddenString`)**: When set to `true`, masks characters as bullets/asterisks as the user types, providing privacy for PINs and sensitive identifiers (source: `akvo-react-form/README.md#question`).
- **Double Entry Verification (`requiredDoubleEntry`)**: When set to `true`, requires the user to enter the same response twice. Submission is blocked until both entries match exactly (source: `akvo-react-form/README.md#question`).

---

## 3. Pre-filled Values in Web Forms (`pre`)

On web forms, an `option` or `multiple_option` field can automatically copy its default selection based on the answer to an earlier source question in the same form session (source: `akvo-react-form/README.md#pre-filled-question`):

| Property | Type | Description |
|---|---|---|
| `source_question` | String | Variable name or ID of the trigger question. |
| `source_answer` | String | Answer value on the source question that triggers the prefill. |
| `default_value` | Array | Array of default option value(s) to automatically assign to this question. |

```json
{
  "pre": {
    "source_question": {
      "source_answer": ["default_value"]
    }
  }
}
```

---

## 4. Extra Content Blocks (`extra`)

The `extra` property attaches custom HTML component blocks before or after a question (source: `akvo-react-form/README.md#extra-component`):

| Property | Type | Description |
|---|---|---|
| `placement` | `"before"` \| `"after"` | Whether content is displayed above or below the question. |
| `content` | String \| Component | HTML string or component containing rich text, guidelines, or links. |
| `translations` | Array | Localized translations for the extra content. |

---

## 5. Validation Rules (`rule` Object)

Configured under the `rule` property for numeric and attachment questions (source: `akvo-react-form/README.md#rule`):

| Rule Key | Supported Types | Description |
|---|---|---|
| `min` | `number` | Minimum allowable numerical value. |
| `max` | `number` | Maximum allowable numerical value. |
| `allowDecimal` | `number` | Allows floating-point numbers (e.g. `3.14`). |
| `allowedFileTypes` | `attachment` | Array of permitted file extensions (e.g. `[".pdf", ".xlsx", ".docx"]`). |
