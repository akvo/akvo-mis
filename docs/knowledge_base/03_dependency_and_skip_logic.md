# Skip Logic & Question Dependency Reference

This document details the conditional dependency and skip logic engine in `akvo-react-form` (source: `akvo-react-form/README.md#dependency-skip-logic`, `akvo-react-form/README.md#dependency-rule-logic`).

---

## 1. Core Principles of Skip Logic

- **Hidden by Default**: If a question has a `dependency` array configured, it is hidden by default. It is only revealed when the trigger conditions evaluate to true (source: `akvo-react-form/README.md#dependency-skip-logic`).
- **Configured on the Dependent Question**: You configure skip logic on the question that should be conditionally revealed, pointing back to the trigger question's ID.
- **Validation Bypass**: When a question is hidden by skip logic, its `required` validation rule is bypassed, and its value is omitted from the submission payload.

---

## 2. Dependency Object Structure

Each element inside the `dependency` array supports the following evaluation properties (source: `akvo-react-form/README.md#dependency-skip-logic`):

| Property | Type | Supported Trigger Types | Description |
|---|---|---|---|
| `id` | Integer \| String | All | The question ID of the trigger question. |
| `equal` | Integer \| String | `input`, `number`, `option` | Condition is met when the trigger question's answer strictly equals this value. |
| `notEqual` | Integer \| String | `input`, `number`, `option` | Condition is met when the trigger question is not blank and not equal to this value. |
| `options` | Array[String] | `option`, `multiple_option` | Condition is met when the selected choice(s) contain any of the listed strings. |
| `min` | Number | `number`, `date` | Condition is met when the numeric answer is greater than or equal to `min`. |
| `max` | Number | `number`, `date` | Condition is met when the numeric answer is less than or equal to `max`. |

---

## 3. Multiple Dependencies: `dependency_rule` (`AND` vs. `OR`)

When a question depends on more than one trigger question, the `dependency_rule` property controls how conditions are combined (source: `akvo-react-form/README.md#dependency-rule-logic`):

- **`"AND"` (Default)**: All dependency conditions in the array must be satisfied for the question to appear.
- **`"OR"`**: The question appears if at least one dependency condition in the array is satisfied.

### Example 1: Multi-Condition with AND Logic
```json
{
  "id": 11,
  "name": "Where do you usually order Rendang from?",
  "type": "option",
  "dependency": [
    { "id": 9, "options": ["Yes"] },
    { "id": 10, "min": 8 }
  ],
  "dependency_rule": "AND",
  "required": true
}
```
*(Source: `akvo-react-form/README.md#example-with-and-logic-default`)*

### Example 2: Multi-Condition with OR Logic
```json
{
  "id": 12,
  "name": "Do you have any dietary restrictions?",
  "type": "text",
  "dependency": [
    { "id": 9, "options": ["Yes"] },
    { "id": 10, "min": 8 }
  ],
  "dependency_rule": "OR",
  "required": false
}
```
*(Source: `akvo-react-form/README.md#example-with-or-logic`)*
