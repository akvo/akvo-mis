# Approvals, Workflows & User Roles

Akvo MIS features a multi-tiered approval engine to ensure data quality and governance before data is published or used in reporting.

---

## 1. Approval Status Lifecycle

Submissions move through the following states in the **Approval Hub**:

```
[Submitted (Pending)] ──► [Approved] (Published to Datasets / Dashboards)
         │
         ├──► [Rejected] (Requires correction / archived)
         │
         └──► [Needs Clarification] (Sent back to enumerator for revision)
```

1. **Pending Approval**: Newly submitted records awaiting supervisor verification.
2. **Approved**: The submission is accepted, committed to the permanent database, and immediately reflected in reports and dashboards.
3. **Rejected**: The submission contains erroneous or duplicate data. It is kept for auditing but excluded from dashboards.

---

## 2. Multi-Level Approval Hierarchies

Akvo MIS supports multi-stage approval chains:
- **Level 1 (Field Supervisor)**: Verifies data completeness and geographic coordinates.
- **Level 2 (District Officer)**: Validates technical indicators and compliance.
- **Level 3 (National / M&E Director)**: Final sign-off for national reporting.

---

## 3. User Roles & Permission Matrix

| Role Name | Access Scope & Permissions |
|---|---|
| **Super Administrator** | Full system access across all tenants, form creation, user management, and system settings. |
| **Tenant Administrator** | Full administrative control within a specific organization/tenant. Manages forms, cascades, and users. |
| **Data Approver / Supervisor** | Reviews, approves, and rejects submissions in the Approval Hub within assigned geographic areas. |
| **Enumerator / Field User** | Submits surveys via mobile app or web form. Can only view and edit their own drafts. |
| **Viewer / Analyst** | Read-only access to approved dashboards, maps, and CSV/Excel exports. |
