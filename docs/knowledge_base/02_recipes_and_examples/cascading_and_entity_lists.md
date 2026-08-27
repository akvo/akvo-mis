# Cascading Lists & Entity Relationships

This document explains how to set up multi-level cascading selectors, administration hierarchies, and entity references in Akvo MIS.

---

## 1. Cascading Questions (`cascade`)

### What is a Cascade?
A cascade is a series of interconnected dropdown menus where each selection filters the options available in subsequent dropdowns.

### Standard Hierarchical Structure
- **Level 1**: Country / Province (e.g. `Province: East Java`)
- **Level 2**: District / Regency (e.g. `District: Malang`)
- **Level 3**: Sub-district / Ward (e.g. `Sub-district: Singosari`)
- **Level 4**: Village / Community (e.g. `Village: Klampok`)

### Configuration Steps
1. **Prepare Data List**: Upload the hierarchical CSV in **Control Centre > Master Data Management > Cascades**.
2. **Add Cascade Question**: In Form Builder, add a question and set type to `Cascade`.
3. **Select Source**: Pick the uploaded cascade dataset from the settings dropdown.
4. **Data Storage**: When submitted, the full path hierarchy is stored as structured attributes, making aggregation and filtering straightforward.

---

## 2. Administration Level Linking (`admin`)

### What is an Administration Question?
In Akvo MIS, tenant administrative boundaries (e.g. Province > District > Sub-district) are managed at the system level.
- When an `admin` question is added to a form, it directly binds the submission to the geographic and organizational boundary tree of the tenant.
- Enables role-based geographic access control (e.g. district supervisors only see data submitted within their assigned district).

---

## 3. Entity Relationships (`entity`)

### What is an Entity in Akvo MIS?
An entity represents a real-world permanent asset or subject (e.g. Water Point, School, Health Clinic, Farmer).
- **Registration Form**: Creates the entity record and assigns its core attributes (GPS location, Name, Identifier).
- **Linked Question**: Forms can include an `entity` question to let enumerators search and select from existing registered entities.
