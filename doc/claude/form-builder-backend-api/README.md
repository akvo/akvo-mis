# Form Builder Backend API (FB-002)

## Overview

This task implements the backend CRUD endpoints for the form builder. It adds form lifecycle management (draft → published), version-on-edit for published forms, and all operations needed by the form builder UI.

**Asana task**: FB-002
**Followed by**: FB-003 [form-builder-integration](../form-builder-integration/README.md) — frontend builds on top of these endpoints

---

## Problem Statement

No write endpoints exist today — all form changes require direct DB or seeder access. This task delivers:
- A form lifecycle: **draft** (editable) and **published** (live, immutable except via versioning)
- Published forms must not be mutated in-place — active submissions must keep referencing the correct schema
- The `Forms.version` field exists but has never been incremented; this task gives it meaning

---

## Scope

| Area | What changes |
|---|---|
| `Forms` model | Add `status` (`DRAFT=1 / PUBLISHED=2`) and `published_at` fields; migration with existing rows → `PUBLISHED` |
| `v1_forms/constants.py` | Add `FormStatus` class |
| New endpoints | `POST /api/v1/forms`, `GET /api/v1/forms/{id}`, `PUT /api/v1/forms/{id}`, `DELETE /api/v1/forms/{id}`, `POST /api/v1/forms/{id}/publish`, `POST /api/v1/forms/{id}/duplicate`, `GET /api/v1/forms/{id}/versions` |
| Existing endpoints | `GET /api/v1/forms` (list) extended to show status/version; `GET /api/v1/form/{id}` (read, used by mobile/web) unchanged |
| Serializers | `FormCreateSerializer`, `FormUpdateSerializer` (partial) |
| Cache | Existing `signals.py` already handles cache eviction on save/delete — no change required |
| Permissions | `IsFormBuilder(BasePermission)` class in `utils/custom_permissions.py`; uses `FeatureAccessTypes.form_builder` |

### Out of Scope

- Frontend form builder pages (FB-003)
- Approval workflow for published forms
- Form archiving UI
- Question attribute (chart/JMP/aggregate) management via editor

---

## Alignment with FB-003

FB-003 (frontend) consumes these endpoints. Both specs must stay in sync:

| Concern | FB-002 (this spec) | FB-003 (frontend) | Aligned? |
|---|---|---|---|
| Create endpoint | `POST /api/v1/forms` | Calls `POST /api/v1/forms` | ✓ |
| Update endpoint | `PUT /api/v1/forms/{id}` | Calls `PUT /api/v1/forms/{id}` | ✓ |
| Request payload | `FormCreateSerializer` schema | `editorToApi()` output | ✓ (see design.md §Contract) |
| Response format | `FormDetailSerializer` (status, version added) | `apiToEditor()` passes through status/version | ✓ |
| `image` type | Only accepted string; `photo` rejected | `editorToApi()` passes `"image"` unchanged | ✓ |
| 201 on PUT (published form) | Returns new form ID | Navigates to `response.data.id` | ✓ |
| Draft status on create | `status=DRAFT` in response | Shows status badge in list | ✓ |

See [design.md § Alignment Notes](design.md) for details.

---

## Documents in This Directory

| File | Purpose |
|---|---|
| [README.md](README.md) | This file — initiative overview |
| [requirements.md](requirements.md) | User AC and functional requirements |
| [design.md](design.md) | Data model changes, API contract, versioning strategy, decisions |
| [implementation-plan.md](implementation-plan.md) | Step-by-step task breakdown |
