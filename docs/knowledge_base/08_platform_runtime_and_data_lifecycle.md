# Platform Execution, Mobile App & Lifecycle

This document describes runtime execution differences between Web and Mobile, the Registration vs. Monitoring data model, and data governance (source: `docs/source/mobileApp.rst`, `docs/source/approval.rst`, `docs/source/dataManagement.rst`).

---

## 1. Web Runtime vs. Mobile App Matrix

| Feature | Web Browser (`akvo-react-form`) | Mobile App (Akvo Flow / AgriConnect) | Key Details |
|---|---|---|---|
| **Form Design** | Full Visual Drag & Drop | View / Fill Only | Form editing is exclusive to the Web Control Centre (source: `docs/source/formBuilder.rst`). |
| **Offline Mode** | Requires active internet | Full Offline Queue | Mobile caches forms and submissions in local SQLite storage (source: `docs/source/mobileApp.rst`). |
| **Registration Pre-fill** | Cross-question in-session (`pre`) | Automatic Native Pre-fill | On mobile, selecting an existing registered data point auto-populates monitoring forms with past registration data. |
| **GPS Geolocation** | Browser Geolocation API | Hardware GPS Chip | Mobile enforces hardware GPS accuracy thresholds (source: `docs/source/mobileApp.rst`). |
| **Camera Capture** | File picker upload | Native In-App Camera | Mobile embeds timestamp and location EXIF metadata into photos. |
| **Barcode / QR Scan** | Manual input | Native Camera Scanner | Mobile scans barcodes directly into text fields (source: `docs/source/mobileApp.rst`). |

---

## 2. Registration vs. Monitoring Lifecycle

Source: `docs/source/formBuilder.rst`, `docs/source/dataManagement.rst`

- **Registration Form**: Creates a new primary entity/location record with permanent identifiers, GPS coordinates, and baseline attributes.
- **Monitoring Form**: Collects recurring longitudinal observations linked to a parent registration record via `parent_id`.
- **Automated Mobile Pre-fill**: When a monitoring form is linked to a registration form in Form Settings, selecting the registered entity on the mobile app automatically fills known baseline details into the monitoring inspection.

---

## 3. Data Governance & Approvals

Source: `docs/source/approval.rst`, `docs/source/dataManagement.rst`

- **Approval Lifecycle**: Submissions progress through `Pending Approval` ➔ `Approved` (published to dashboards/reports) or `Rejected` / `Needs Clarification`.
- **In-Line Grid Editing**: Authorized administrators can correct typos or data points directly in **Control Centre > Data Management** without re-submitting.
- **Multi-Level Approval**: Supports multi-stage hierarchical review (Field Supervisor ➔ District Officer ➔ National Director).
