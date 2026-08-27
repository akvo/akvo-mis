# Calculation Formulas & Autofield Reference

Autofields (`autofield`) compute values automatically based on other question answers in real time during form completion.

## Formula Syntax & Rules

1. **Referencing Variables**:
   - Variables are referenced using square brackets: `[variable_name]`.
   - The referenced variable must exist in the form before the autofield and must have a valid unique variable name.
2. **Supported Operators**:
   - Addition: `+`
   - Subtraction: `-`
   - Multiplication: `*`
   - Division: `/`
   - Parentheses: `(` and `)` for grouping and precedence.

---

## Practical Formula Examples

### 1. Simple Total Cost
- **Question 1**: `unit_price` (`number`) — Price per item.
- **Question 2**: `quantity` (`number`) — Number of items purchased.
- **Autofield Question**: `total_amount`
  - **Formula**: `[unit_price] * [quantity]`
  - **Display**: Shows computed total cost instantaneously as numbers are typed.

### 2. Body Mass Index (BMI) Calculation
- **Question 1**: `weight_kg` (`number`) — Weight in kilograms.
- **Question 2**: `height_m` (`number`) — Height in meters (e.g. 1.75).
- **Autofield Question**: `bmi_score`
  - **Formula**: `[weight_kg] / ([height_m] * [height_m])`

### 3. Total Area Aggregation
- **Question 1**: `plot_length_m` (`number`) — Length of plot in meters.
- **Question 2**: `plot_width_m` (`number`) — Width of plot in meters.
- **Autofield Question**: `area_sq_meters`
  - **Formula**: `[plot_length_m] * [plot_width_m]`

### 4. Percentage Score Calculation
- **Question 1**: `actual_score` (`number`) — Points earned.
- **Question 2**: `max_score` (`number`) — Total possible points.
- **Autofield Question**: `percentage_achieved`
  - **Formula**: `([actual_score] / [max_score]) * 100`

---

## Best Practices & Troubleshooting
- **Null / Empty Values**: If a referenced question has not yet been answered by the user, the autofield calculation waits until all prerequisite inputs have valid numbers.
- **Division by Zero**: Avoid zero denominator inputs or use skip logic to ensure the denominator is greater than zero before displaying the autofield.
