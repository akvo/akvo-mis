# DO-001: Data Onboarding from a Spreadsheet

**Task ID**: DO-001
**GitHub Issue**: [#573](https://github.com/akvo/akvo-mis/issues/573)
**Date**: 2026-11-16
**Status**: Draft

Terms (Tenant, Data Onboarding, Proposal, Apply, Onboarding Report, Ambiguous Administration) are defined in `/GLOSSARY.md`. The core decision is recorded in `doc/adr/0001-llm-drafts-proposal-code-applies-it.md`.

---

## 1. Context & Problem Statement

Data teams bring an Excel or CSV file and want to see it in MIS for a demo or PoC. Setting up the administration, building the forms and loading the records by hand takes too many steps (#461).

PR #462 solved this with an external Claude skill that registered a new workspace. #525 (MT-029, captcha on tenant creation) blocks automated registration, so that path no longer works. Only its spreadsheet analysis and loading rules carry over. This feature moves the work in-app, into an **existing** tenant, and uses OpenAI, which the backend already uses for visualization AI and the chatbot.

## 2. Requirements

### User Acceptance Criteria

- A user with the `data_onboard` access sees **Onboard spreadsheet** on the Forms list. Tenant super admin has it by default.
- The user uploads one CSV or xlsx file (multi-sheet allowed, ≤ 10 MB, ≤ 50k rows).
- MIS shows progress while it drafts the Proposal, then shows the Proposal for review:
  - administration units to add,
  - each form, question by question,
  - which column feeds which question,
  - what will not be loaded, and why,
  - any Ambiguous Administration that blocks a form.
- The user changes the Proposal by:
  - structured edits, limited to resolving ambiguity (pick level mapping, alias, parent), keeping or dropping columns, and renaming forms,
  - a free-text "revise with instruction" box, which re-drafts via OpenAI.
- Nothing is written to the tenant until the user approves. Apply then:
  - adds the approved units,
  - creates and publishes the new forms,
  - loads the records as approved data.
- When Apply completes or fails, the user gets an email with a summary and a link. The full Onboarding Report is in-app and downloadable. Past Data Onboardings are listed with who ran them and when.
- Forms blocked by ambiguity can't be applied. The other forms in the same Proposal can.

### Technical Acceptance Criteria

- OpenAI receives only the column profile: column names, types, value shapes, and the distinct values of category-like columns (at most 30 distinct values). Values from other columns never leave MIS (ADR 0001).
- The ambiguity checks are deterministic. They run on every draft and revision, and **again at Apply**.
- Setup (units + forms) runs in one transaction. Data rows are best-effort: a bad row is skipped and reported, and the rest load.
- Proposal drafting and Apply run as Django-Q jobs. The client polls their status.
- OpenAI output is validated against the Proposal format before it is stored. Invalid output fails the draft.
- Every endpoint checks the Data Onboarding permission on the server. Hiding the button in the UI is not the protection.
- There is a per-tenant cap on drafts and revisions (default 20/day). The model is configurable in settings next to `OPENAI_API_KEY`.
- The uploaded file is deleted after Apply, or after 14 days if the Proposal is abandoned. The Proposal and Report are kept. The Report holds row numbers and reasons, not row contents.

## 3. Scope Rules

| Rule | Decision |
|---|---|
| Target tenant | Any existing tenant, fresh or populated |
| Forms | Always **new** forms. A name clash with an active form shows in the Proposal and blocks that form until the user renames it or archives the old form. Archived forms do not clash. Loading into existing forms is out of scope |
| Monitoring forms | Parent must be a registration form in the **same** Proposal |
| Re-run | One-shot. No top-up of forms after Apply. To redo, archive the created forms and onboard again: forms with data can't be deleted, only archived. Archiving needs the existing `form_publish` access, which the Data Onboarding permission does not include. An importer without it needs a super admin to archive |
| New levels | Only on a tenant whose tree is just the root, and only by super admin |
| New units | Proposed under a matched parent, listed in the Proposal, created on approval |
| Non-super-admin importer | Confined to the subtree of their role's administration. Rows outside it are skipped and reported, and do not count as ambiguous |
| New forms' approval | No approvers. Data visibility follows the normal role rules. Approvers are set later in the form builder |
| Data state | Loaded as approved records, bypassing pending and approval |

### Ambiguous Administration

Each of these blocks the affected form:

1. Location columns can't be mapped one-to-one onto existing levels: a column missing in the middle, or more columns than levels.
2. A unit name exists under more than one parent, and the row has no parent column to disambiguate.
3. A near-match spelling (normalized name + edit distance) would otherwise create a duplicate unit.
4. A registration sheet has no location column.

The LLM may suggest aliases and mappings. The deterministic checks decide.

## 4. Proposal Format

- **Forms** use the canonical form definition format accepted by `manage/forms/import` (`import_definition`). Apply creates forms through that existing path, so there is no second form-creation code.
- **Administration and data mapping** follow #462's `plan.json` sections: `administration` (levels, source columns, units, aliases) and `data[]` (key columns, administration columns, geo, column map, value maps, date format, multi-separator, unmapped columns).
- The loading rules carry over from #462's `reference/plan-format.md`:
  - a required answer that is blank or invalid skips the row,
  - an optional answer that is invalid is dropped with a warning,
  - key columns give a stable uuid and link monitoring rows to their parent,
  - option values are derived from labels.
- Value maps are possible only for category-like columns (at most 30 distinct values), because only their values reach OpenAI.

## 5. Data Model Changes

To be designed. Likely a tenant-scoped `DataOnboarding` record holding:
- status,
- the uploaded file reference,
- the column profile,
- the Proposal JSON and its revisions,
- the Report,
- the created-by user,
- timestamps.

Plus constants:
- `FeatureTypes.data_onboarding`,
- `FeatureAccessTypes.data_onboard`, numbered after 12 (existing values are persisted, so they are never reused).

## 6. API Contract

To be designed: upload → draft (job), get status and Proposal, structured edit, revise (job), apply (job), get Report, download Report, list past Data Onboardings.

## 7. Compatibility

- Mobile: published forms sync as usual. No app change.
- Existing imports (XLSForm, form definition, bulk administrations) are unchanged.

## 8. Security Considerations

- Every upload is a trust boundary. Validate type, size and row count before parsing.
- Data sent to OpenAI is limited to the profile. Category values can still be sensitive, for example a health status column (see Open Questions).
- All reads and writes are tenant-scoped. Subtree enforcement applies to non-super-admin importers.

## 9. Testing Strategy

- Primary seam: the Data Onboarding HTTP API, with OpenAI, background jobs and file storage faked. It covers the full flow from upload to Report: units, forms, record counts and Report reasons.
- A test seeds a high-cardinality column with marker values and asserts that none of them reach the OpenAI request.
- Secondary seam: one check-and-apply service function, with table tests for the ambiguity checks (cases 1–4) and the row rules.
- No separate tests for the profiler, the prompt or form creation. Form creation reuses the form definition import and its tests.

## 10. Open Questions

- Should the review offer a per-column "never send to OpenAI" control for sensitive category-like columns?
- Revision history: keep every Proposal revision, or only the latest?

## 11. References

- #461, PR #462 (`skills/akvo-mis-workspace-from-data/reference/plan-format.md` on branch `feature/461-workspace-from-spreadsheet-skill`)
- MT-029 (#525) signup and auth abuse hardening
- FB-007 form import/export, FB-016 XLSForm import
- MT-007 administration bulk upload hardening
