# Form Design Recipes & Real-World Templates

This guide provides concrete, field-tested form design patterns and recipes for common data collection scenarios in Akvo MIS.

---

## Recipe 1: Water Facility Inspection & Condition Audit

### Goal
Collect inspection data on a rural water supply point with status color-coding, GPS coordinates, and conditional maintenance workflows.

### Structure & Questions
1. **Facility Identification (Question Group: Basic Info)**:
   - `facility_name` (`input`): Label = "Facility Name", `required = true`.
   - `facility_code` (`input`): Label = "Asset Barcode/ID", `addonBefore = "WP-"`, `double_entry = true`.
   - `location` (`geo`): Label = "GPS Coordinates", `required = true`.
2. **Operational Status (Question Group: Technical Assessment)**:
   - `status` (`option`): Label = "Current Operational Status", `required = true`. Choices:
     - `functional`: Label = "Functional (Good)", `color = "#28A745"` (Green).
     - `partially_functional`: Label = "Partially Functional (Needs Service)", `color = "#FFA500"` (Orange).
     - `non_functional`: Label = "Non-Functional (Broken)", `color = "#DC3545"` (Red).
3. **Repair Requirements (Question Group: Maintenance Plan)**:
   - `broken_parts` (`multiple_option`): Label = "Damaged Components", choices = `["Pump handle", "Cylinder", "Pipes", "Apron crack"]`.
     - *Skip Logic*: Show only if `status != "functional"`.
   - `estimated_repair_cost` (`number`): Label = "Estimated Repair Cost", `addonBefore = "$"`, `addonAfter = "USD"`, `min = 0`.
     - *Skip Logic*: Show only if `status == "non_functional"`.
   - `inspector_signature` (`signature`): Label = "Inspector Sign-Off", `required = true`.

---

## Recipe 2: Household Socio-Economic Baseline Survey

### Goal
Collect demographic data, household size, and agricultural asset inventory using repeatable groups and calculations.

### Structure & Questions
1. **Household Profile**:
   - `head_name` (`input`): Label = "Household Head Full Name", `required = true`.
   - `phone_number` (`input`): Label = "Contact Number", `addonBefore = "+254"`, `max_length = 10`.
   - `num_members` (`number`): Label = "Total Household Members", `min = 1`, `max = 30`.
2. **Household Roster (Repeatable Group: Family Members)**:
   - *Group Settings*: `Repeatable = true` (allows enumerator to click "+ Add Member" for each person).
   - `member_name` (`input`): Label = "Member Name".
   - `member_age` (`number`): Label = "Age in Years", `min = 0`, `max = 120`.
   - `member_gender` (`option`): Label = "Gender", choices = `["Male", "Female", "Other"]`.
3. **Economic Summary**:
   - `monthly_income` (`number`): Label = "Estimated Monthly Income", `addonBefore = "$"`
   - `income_per_capita` (`autofield`): Label = "Income Per Capita", formula = `[monthly_income] / [num_members]`.

---

## Recipe 3: Multi-Language Form with Translations Tab

### Workflow
1. Build the base form in English in the **Edit Form** tab.
2. Switch to the **Translations** tab in the top workspace bar.
3. Select the target language from the language selector (e.g. French / Indonesian / Swahili).
4. Fill in translated text for each question label, tooltip, and option choice:
   - Example: English `"What is your name?"` ➔ French `"Quel est votre nom?"`.
5. When respondents open the web form or mobile form, they can toggle their preferred language from the top bar.
