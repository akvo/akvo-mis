# Data Management, Cleaning & Export Formats

This guide covers data cleaning, batch editing, and export capabilities (CSV, JSON, XLSForm) in Akvo MIS.

---

## 1. Data Cleaning & Batch Updates

Located in **Control Centre > Data Management**:
- **Grid View & Filtering**: Filter records by date range, enumerator, administration level, or approval status.
- **In-Line Editing**: Authorized administrators can correct typos or missing values directly in the data grid without altering historical audit timestamps.
- **Batch Status Updates**: Bulk approve or reject multiple submissions simultaneously.

---

## 2. Export Formats & Options

### CSV & Excel Export
- Generates tabular spreadsheets containing all question variables as columns.
- **Repeatable Groups Handling**: Repeatable groups (e.g. household members) can be exported as separate linked sheets with parent record IDs for relational analysis.
- **Geographic Data**: Latitude and Longitude are exported as discrete floating-point columns (`latitude`, `longitude`) ready for GIS software (QGIS, ArcGIS).

### JSON Schema & Data Export
- **Form Definition Schema**: Download raw JSON schema definitions for backup or programmatic deployment.
- **Submission Payloads**: Full JSON payloads available via the Akvo MIS REST API (`/api/v1/data/`).

### XLSForm Export & Import
- **Import XLSForm**: Upload an industry-standard XLSForm Excel file (`.xlsx`) containing `survey`, `choices`, and `settings` sheets to generate a new Akvo MIS form instantly.
- **Export XLSForm**: Download any Akvo MIS form as an XLSForm-compatible file for sharing across external survey tools (ODK, KoboToolbox).
