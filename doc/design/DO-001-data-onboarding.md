# DO-001: Data Onboarding from a Spreadsheet

**Task ID**: DO-001
**GitHub Issue**: [#573](https://github.com/akvo/akvo-mis/issues/573)
**Date**: 2026-11-16
**Status**: Implemented

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
- When Apply completes or fails, the user gets an email with a summary and a link. The full Onboarding Report is in-app and downloadable. Past Data Onboardings are listed with who started them and when.
- Forms blocked by ambiguity can't be applied. The other forms in the same Proposal can.

### Technical Acceptance Criteria

- OpenAI receives only the column profile: column names, types, value shapes, and the distinct values of category-like columns (at most 30 distinct values, and at most half as many distinct values as filled cells). Values from other columns never leave MIS (ADR 0001).
- The ambiguity checks are deterministic. They run on every draft and revision, and **again at Apply**.
- Setup (units + forms) runs in one transaction. Data rows are best-effort: a bad row is skipped and reported, and the rest load.
- Proposal drafting and Apply run as Django-Q jobs. The client polls their status.
- OpenAI output is validated against the Proposal format before it is stored. Invalid output fails the draft.
- Every endpoint checks the Data Onboarding permission on the server. Hiding the button in the UI is not the protection.
- There is a per-tenant cap on Proposals and revisions (default 20/day). The model is configurable in settings next to `OPENAI_API_KEY`.
- The uploaded file is deleted after Apply, or after 14 days if the Proposal is abandoned. The Proposal and Report are kept. The Report holds row numbers and reasons, not row contents.

## 3. Scope Rules

| Rule | Decision |
|---|---|
| Target tenant | Any existing tenant, fresh or populated |
| Forms | Always **new** forms. A name clash with an active form shows in the Proposal and blocks that form until the user renames it or archives the old form. Archived forms do not clash. Loading into existing forms is out of scope |
| Monitoring forms | Parent must be a registration form in the **same** Proposal |
| Re-run | One-shot. No top-up of forms after Apply. To redo, archive the created forms and onboard again: forms with data can't be deleted, only archived. Archiving needs the existing `form_publish` access, which the Data Onboarding permission does not include. An importer without it needs a super admin to archive |
| New levels | Only on a tenant whose tree is just the root, and only by super admin |
| New units | Read from the file's location columns under a matched parent, listed in the review, created on approval |
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
- **Administration and data mapping** follow #462's `plan.json` sections: `administration` (levels, source columns, aliases) and `data[]` (key columns, administration columns, geo, column map, value maps, date format, multi-separator, unmapped columns).
- The loading rules carry over from #462's `reference/plan-format.md`:
  - a required answer that is blank or invalid skips the row,
  - an optional answer that is invalid is dropped with a warning,
  - key columns give a stable uuid and link monitoring rows to their parent,
  - option values are derived from labels.
- Value maps are possible only for category-like columns (at most 30 distinct values, and at most half as many distinct values as filled cells), because only their values reach OpenAI.

## 5. Data Model Changes

App `api/v1/v1_data_onboarding`. One tenant-scoped model, `DataOnboarding` (table `data_onboarding`):

| Field | Holds |
|---|---|
| `tenant` | Owning tenant |
| `status` | `drafting`, `proposed`, `applying`, `applied`, `failed` (a revision shows as `drafting`; a failed revision returns to `proposed`) |
| `file`, `file_name` | Storage path of the upload (purged after Apply, or after 14 days) and its original name |
| `profile` | The column profile, all OpenAI ever sees of the file |
| `proposal` | The latest Proposal only. A revision or edit replaces it; earlier ones are not kept |
| `blocked` | Forms the ambiguity checks block, with their causes. Holds names from the file, so it is never part of the Proposal |
| `resolutions` | Review choices that settle ambiguity (level of the first location column, parent, alias, confirmed new unit). Holds names from the file, so it is never part of the Proposal |
| `revised` | Timestamps of revisions, counted against the daily cap |
| `report` | The Onboarding Report: forms with records loaded, skipped rows and dropped answers, and blocked forms with cause kind and reason only. No cell values |
| `error` | Why the last draft, revision or Apply failed |
| `created_by`, `created`, `updated` | Who started it, and when |

Plus constants:
- `FeatureTypes.data_onboarding` (4),
- `FeatureAccessTypes.data_onboard` (13), numbered after 12 (existing values are persisted, so they are never reused).

A Django-Q schedule (migration `0002`) purges uploads hourly.

## 6. API Contract

All under `/api/v1/data-onboarding`, behind `DataOnboardingAccess` and scoped to the caller's tenant. Jobs run in Django-Q; the client polls the detail endpoint.

| Method and path | Does |
|---|---|
| `GET /data-onboarding` | List past Data Onboardings: id, status, file name, started by, created, updated |
| `POST /data-onboarding` | Upload one CSV or xlsx (`file`). Validates type, size and rows, counts against the daily cap (429 over it), queues the draft job. 201 with the detail |
| `GET /data-onboarding/<id>` | Detail: status, Proposal, `blocked`, `resolutions`, Report, error, started by. When proposed, also `units`: `{new, outside}`, the name paths of units Apply would add for the viewer and those outside the viewer's subtree, read from the file. In-app only: never stored, never sent to OpenAI |
| `POST /data-onboarding/<id>/edits` | One structured edit, `{"op": ..., ...}`: `rename_form`, `drop_column`, `keep_column`, `map_level`, `set_location_column`, `drop_form`, `choose_parent`, `resolve_near_match`. Proposed only. No OpenAI call; all checks re-run for the acting user |
| `POST /data-onboarding/<id>/revise` | `{"instruction": ...}` (≤ 2,000 characters). Queues a re-draft through OpenAI from the profile and the Proposal only. Counts against the cap |
| `POST /data-onboarding/<id>/apply` | Optional `{"forms": [keys]}` (default: all unblocked). Queues Apply for the acting user. Proposed only |
| `GET /data-onboarding/<id>/report` | The Onboarding Report as xlsx |

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
- ~~Revision history: keep every Proposal revision, or only the latest?~~ Only the latest (D-5).

## 11. References

- #461, PR #462 (`skills/akvo-mis-workspace-from-data/reference/plan-format.md` on branch `feature/461-workspace-from-spreadsheet-skill`)
- MT-029 (#525) signup and auth abuse hardening
- FB-007 form import/export, FB-016 XLSForm import
- MT-007 administration bulk upload hardening

## 12. Decision Log

- **D-1 Access needs `form_view` too.** "Onboard spreadsheet" shows only with both `form_view` and `data_onboard`; the Forms list gates stay as they are.
- **D-2 The importer sees what they loaded.** Apply adds a `UserForms` row for the applying user on each new form.
- **D-3 Tighter profile value rule.** A column sends its values only with ≤ 30 distinct values that repeat (distinct ≤ half the filled cells). Unique-per-row columns never send values.
- **D-4 File values stay out of the Proposal.** Ambiguity findings (`blocked`) and review choices (`resolutions`) live beside the Proposal, because a revision resends the Proposal to OpenAI. The units shown in the review are computed from the file per request and never stored. The Report keeps blocked forms' cause kind and reason only.
- **D-5 One edit endpoint, checks on every change.** Every draft, revision and edit re-runs validation, the hierarchy check and the ambiguity checks before it is stored. Only the latest Proposal is kept (answers the revision-history question).
- **D-6 A failed revision keeps the previous Proposal** and stays proposed, with the error shown.
- **D-7 Checks run for the acting user.** Edits, revisions and Apply use the scope and rights of the user making the request, not of the user who started the Data Onboarding.
- **D-8 New levels only on a bare tree.** Adding levels is refused when the tenant has any level below the root, and for anyone but a super admin.
- **D-9 Multi-select separator is a set of characters.** Each character of `multi_separator` splits a cell; parts are trimmed. It is not a pattern.
- **D-10 Rows load in savepoints.** Any error in a row skips only that row ("This row could not be loaded."); the rest load.
- **D-11 Code places the location, not the model.** The Proposal has no unit list: the units to add are read from the file's location columns. Models drafted bare names (a village as a province) and mapped the location columns to the administration question instead of `administration_columns`; such columns are moved there before the checks run. Models also "corrected" known names to ones they guessed ("Jakarta" to "DKI Jakarta"), which would add duplicates: an alias is kept only from an unknown spelling to an existing unit or a listed value of a location column.
