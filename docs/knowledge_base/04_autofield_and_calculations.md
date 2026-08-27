# Autofield & Calculation Formulas Reference

This document describes the autofield calculation syntax, security model, and formula examples in `akvo-react-form` (source: `akvo-react-form/README.md#autofieled-object`).

---

## 1. Autofield Object Structure

An autofield question calculates its value dynamically in the web runtime via a JavaScript function string defined in the `fn` property (source: `akvo-react-form/README.md#autofieled-object`):

| Property | Type | Description |
|---|---|---|
| `fnString` | String | String containing the JavaScript calculation function. |
| `multiline` | Boolean | Whether the function contains multiple lines or complex branching. |
| `fnColor` | Object | Optional map of answer values to hex background colors (e.g. `{"High Risk": "#FECDCD", "Low Risk": "#CCFFC4"}`). |

---

## 2. Function Syntax & `#N` Variable Referencing

- **`#N` Prefix**: Used to reference the live answer value of **question ID `N`** (source: `akvo-react-form/README.md#autofieled-object`).
- **Security & Sanitization**: The runtime does **NOT** use `eval()`. The function string is strictly sanitized and compiled in a secure sandbox before execution.

### Standard Function Formats:
```javascript
function () { return #1 / #2 }
```
OR using arrow function syntax:
```javascript
() => { return #1.includes("Test") ? #2 / #3 : 0 }
```
*(Source: `akvo-react-form/README.md#autofieled-object`)*

---

## 3. Practical Calculation Recipes

### Recipe 1: Total Cost Aggregation
- Question `#10`: Unit Price (`number`)
- Question `#11`: Quantity (`number`)
- Autofield `#12`:
```javascript
function () { return #10 * #11 }
```

### Recipe 2: Body Mass Index (BMI)
- Question `#20`: Weight in kg (`number`)
- Question `#21`: Height in meters (`number`)
- Autofield `#22`:
```javascript
function () { return #20 / (#21 * #21) }
```

### Recipe 3: Percentage Score
- Question `#30`: Score earned (`number`)
- Question `#31`: Total possible (`number`)
- Autofield `#32`:
```javascript
function () { return (#30 / #31) * 100 }
```

---

## 4. Conditional Output Styling (`fnColor`)

You can automatically style the computed output badge using `fnColor` (source: `akvo-react-form/README.md#autofieled-object`):
```json
{
  "fnColor": {
    "Pass": "#CCFFC4",
    "Fail": "#FECDCD"
  }
}
```
