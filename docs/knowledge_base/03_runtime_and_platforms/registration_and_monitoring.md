# Registration & Monitoring Form Lifecycle

Akvo MIS organizes continuous longitudinal data collection through **Registration** and **Monitoring** form pairs.

---

## 1. Registration Forms

### Purpose
A Registration Form establishes the baseline record for an entity or physical asset (e.g. a water point, a school, a healthcare clinic, or a farmer).

### Key Characteristics
- **Creates a New Entity**: Every submission generates a new unique record with a permanent `data_point_id` or `entity_id`.
- **Collects Static Attributes**: Typically captures attributes that rarely change, such as:
  - Permanent Entity Name / Code
  - GPS Location (Latitude, Longitude)
  - Installation / Construction Date
  - Facility Type / Category

---

## 2. Monitoring Forms

### Purpose
A Monitoring Form tracks the changing condition, operational status, and routine measurements of an existing registered entity over time.

### Key Characteristics
- **Linked via `parent_id`**: A monitoring submission is always tied to a specific parent registration record.
- **Collects Dynamic Data**: Captures time-series observations, such as:
  - Current operational status (e.g. Functional, Broken)
  - Water flow rate, water quality tests
  - Maintenance history, inspection notes
  - Monthly attendance, revenue figures

---

## 3. Mobile Pre-fill Workflow

### How Mobile Pre-fill Works
1. When an enumerator opens the Akvo MIS mobile app, they see a map or list of registered data points.
2. The enumerator selects a specific entity (e.g. "Borehole #104").
3. When clicking **"Start Monitoring"**, the mobile app automatically pulls known registration information (such as the Facility Name and GPS coordinates) into read-only display fields.
4. The enumerator only has to answer the new monitoring questions for today's inspection.

### Configuration in Akvo MIS
- You do **not** need to write complex formulas or code in the Form Builder to achieve this.
- In **Control Centre > Form Builder > Form Settings**, simply link the Monitoring Form to its corresponding Registration Form. The mobile application handles the automated pre-filling natively.
