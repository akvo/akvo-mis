# Skip Logic (Conditional Dependencies) Reference Matrix

Skip logic conditionally reveals or hides questions based on answers given to earlier trigger questions.

## Core Principles of Skip Logic
1. **Configured on the Dependent Question**: You always open the settings on the question that should be **revealed**, not on the trigger question.
2. **Hidden Questions are Cleared**: If a question is hidden by skip logic, its value is excluded from submission and validation (i.e. `required` rules are ignored when hidden).
3. **No Forward Dependencies**: A trigger question must always appear **before** the dependent question in the form layout.

---

## Supported Logic Operators

| Operator | Symbol / Keyword | Applicable Question Types | Behavior | Concrete Example |
|---|---|---|---|---|
| **Equal** | `=` / `equal` | `option`, `input`, `number` | Reveals question when the answer exactly matches the specified value. | If `has_solar_panel == "yes"`, reveal `solar_capacity_kw`. |
| **Not Equal** | `!=` / `not_equal` | `option`, `input`, `number` | Reveals question when the answer is anything other than the specified value. | If `payment_status != "paid"`, reveal `reason_for_delay`. |
| **Contains** | `contains` | `multiple_option`, `input`, `text` | Reveals question when the selected choices or text include the specified substring. | If `crops_grown` contains `"rice"`, reveal `rice_field_area_ha`. |
| **Greater Than** | `>` / `greater_than` | `number`, `date`, `autofield` | Reveals question when numeric answer is strictly greater than the threshold. | If `household_members > 5`, reveal `overcrowding_notes`. |
| **Less Than** | `<` / `less_than` | `number`, `date`, `autofield` | Reveals question when numeric answer is strictly below the threshold. | If `water_ph_level < 6.5`, reveal `acidity_remediation_plan`. |
| **Between** | `between` / `min_max` | `number`, `date` | Reveals question when numeric value falls within a closed interval `[min, max]`. | If `child_age` between `0` and `5`, reveal `vaccination_record`. |

---

## Advanced Skip Logic Patterns

### 1. Multi-Condition Logic (Stacking Rules)
- A single question can depend on multiple conditions.
- **Evaluation**: The conditions are evaluated collectively. If any condition is satisfied, the question is revealed.
- *Example*: Show `detailed_irrigation_questions` if `farm_type == "commercial"` OR `water_source == "borehole"`.

### 2. Cascading Show/Hide Chains
- Question A triggers Question B, and Question B triggers Question C.
- *Best Practice*: Keep chains shallow (1–3 levels max) to prevent user confusion and maintain form performance.

### 3. Duplicate / Copy Question Workflow
- In the Form Builder, clicking **"COPY QUESTION HERE"** duplicates the question type, label, tooltip, choices, and settings immediately below the source card.
- **Important**: Skip logic rules are **NOT** copied to avoid accidental dependency conflicts. You must configure skip logic explicitly on the new duplicate question.
- **Variable Name**: The duplicate question copies the variable name; ensure you rename the variable name to maintain uniqueness across the form.
