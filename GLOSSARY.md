# Akvo MIS

A multi-tenant management information system: organisations define forms over an administration hierarchy and collect, approve and visualise data against it.

## Tenancy

**Tenant**:
One organisation's isolated space in MIS, with its own users, administration, forms and data.
_Avoid_: Workspace (UI copy only), account, organisation

## Data Onboarding

**Data Onboarding**:
Turning a data team's existing spreadsheet into new administration units, new forms and loaded records inside a tenant. The spreadsheet may instead be a Form Definition, which gives forms only.
_Avoid_: Spreadsheet import, AI form builder, import (taken by XLSForm and form definition import)

**Form Definition** (in Data Onboarding):
A spreadsheet that describes a questionnaire rather than holding records: an XLSForm, an Akvo Flow export, a paper survey, a question list.
_Avoid_: Template, form file

**Proposal**:
The drafted setup of a Data Onboarding (units to add, forms, column-to-question mapping, what is dropped), which the user reviews and approves.
_Avoid_: Plan, draft

**Apply**:
Executing an approved Proposal against the tenant.
_Avoid_: Run, execute, commit

**Onboarding Report**:
The outcome of an Apply: records loaded per form, and every skipped row or dropped answer with its reason.
_Avoid_: Load report, import log

**Ambiguous Administration**:
A state where spreadsheet locations cannot be placed in the hierarchy with certainty, which blocks the affected form from Apply until the user resolves it.
_Avoid_: Unmatched location, admin conflict
