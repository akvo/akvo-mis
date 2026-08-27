# Validation Rules, Modifiers & Advanced Properties

This document explains every validation rule, input modifier, and schema property available across the Akvo MIS Form Builder and runtime engine.

## Universal & Common Properties

| Property | Supported Types | UI Location | Purpose & Details | Example |
|---|---|---|---|---|
| `label` | All types | Question Card Header | The human-readable question prompt displayed to respondents. | `"What is the primary source of drinking water?"` |
| `name` / `variable_name` | All types | Settings Panel > General | Unique identifier used for column names in exports, API payloads, and formula references. Cannot contain spaces. | `water_source_type` |
| `tooltip` | All types | Settings Panel > General | Descriptive instruction or guidance displayed underneath the question label to assist enumerators. | `"Observe the main water container used by the household."` |
| `required` | All types | Settings Panel > Validation | If checked (`true`), the form prevents submission until answered. Note: Required rules are skipped when a question is hidden by skip logic. | `true` |
| `disabled` / `readonly`| All types | Settings Panel / JSON | Makes the field un-editable by the user. Commonly used for autofields or prefilled reference values. | `false` |

---

## Input Modifiers & Context Helpers

### 1. Prefix (`addonBefore`) and Suffix (`addonAfter`)
- **Supported On**: `input` (text) and `number` fields only.
- **Rules**:
  - Accepts plain text strings and standard unicode symbols (e.g. `+62`, `$`, `kg`, `cm`, `%`, `m²`).
  - **No Images or Icons**: Graphic icons, image tags, or font-awesome classes are not supported.
- **Best Use Cases**:
  - `addonBefore`: Currency indicators (`$`, `€`), country calling codes (`+62`, `+254`), ID prefix labels (`ID:`).
  - `addonAfter`: Units of measurement (`kg`, `cm`, `hectares`, `litres/day`, `percent`).

### 2. Password Masking (`mask` / `password`)
- **Supported On**: `input` (text) fields only.
- **Functionality**: Masks entered characters as bullets/dots to conceal sensitive input on-screen. A toggleable eye icon allows the respondent to momentarily view the text if needed.
- **Best Use Cases**: Secret security codes, sensitive personal ID numbers, temporary PINs.

### 3. Double Entry Verification (`double_entry`)
- **Supported On**: `input` (text) and `number` fields.
- **Functionality**: Prompts the respondent or enumerator to enter the answer a second time in a confirmation box. If the two entries do not match exactly, submission is blocked.
- **Best Use Cases**: Critical figures where typo prevention is paramount (e.g. National Identification Number, Bank Account Number, Land Area in hectares).

### 4. Option Choice Hex Color Tags (`options[].color`)
- **Supported On**: `option` (Single Choice) and `multiple_option` (Multiple Choice).
- **Functionality**: Displays a colored badge or pill tag next to the choice in web forms.
- **Color Format**: Standard 6-character hex code starting with `#` (e.g. `#28A745` for green, `#DC3545` for red, `#FFA500` for orange).
- **Behavior**: Purely a visual cue to speed up data entry and review. Does NOT alter how data is exported or calculated.

### 5. Extra Content Blocks (`extra.before` and `extra.after`)
- **Supported On**: All question types via Form JSON schema.
- **Functionality**: Inserts rich HTML content blocks directly above (`extra.before`) or below (`extra.after`) the question.
- **Difference from Addons**:
  - `addonBefore`/`addonAfter` = Inline text labels right next to the text/number input box.
  - `extra.before`/`extra.after` = Full-width HTML content containers for instructional text, external documentation links, or explanatory infographics.

---

## Validation Bounds & Constraints

### 1. Numeric Min/Max Bounds
- **Min Value (`min`)**: Rejects any number strictly smaller than the specified limit.
  - *Example*: Age in years: `min = 0`.
- **Max Value (`max`)**: Rejects any number strictly larger than the specified limit.
  - *Example*: Percentage: `min = 0, max = 100`.

### 2. Character Length Validation
- **Max Length (`max_length`)**: Restricts the maximum number of characters allowed in text fields.
  - *Example*: 10-digit phone number: `max_length = 10`.

### 3. Date Range Constraints
- Configures allowable start and end date ranges to prevent illogical data entry (e.g. preventing future dates for historical inspection dates).
