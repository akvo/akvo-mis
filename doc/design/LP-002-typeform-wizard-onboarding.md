# Feature Design Document — Typeform-style Wizard Onboarding

> **Purpose**: Replace the landing CTA target (the bare `/register` form) with a
> pleasant, one-question-at-a-time wizard that wraps the **existing** two-phase
> registration and auto-configures the workspace. Second of three:
> **[[LP-001]]** landing · **LP-002 (this)** wizard · **[[LP-003]]** AI onboarding.

---

## Feature: Guided Wizard Onboarding (phase 1)

**Task ID**: LP-002
**Author**: Iwan Firmawan
**Date**: 2026-11-11
**Status**: Review
**Estimate**: ~8h (agentic coding; ports the approved wizard prototype)
**Depends on**: [[LP-001]] (landing page + CTA)

---

## 1. Context & Problem Statement

```
Currently (after LP-001):
- The landing CTA funnels to the existing MT-006 sign-up: a bare form
  (`/register`) → email activation → a separate `/configure` form the user
  must fill before the dashboard is reachable.
- It works, but it is two dense forms with a gap in between — not the
  "try it yourself" experience the landing page promises.

Goal:
- A Typeform-style wizard (one question per screen, progress, Back/Next) that
  collects the same fields, creates the tenant through the EXISTING flow, and
  pre-fills `/configure` so the visitor lands in a usable control center after
  activation — never seeing the raw configure form.
- No new provisioning path, no weakened email verification: the wizard is UX
  over an unchanged backend, plus one tiny read-only helper.
```

---

## 2. Requirements

### User Acceptance Criteria
- [ ] Clicking the landing CTA starts a step-by-step wizard (one question per
      screen, progress indicator, Back/Next), not a dense form.
- [ ] The wizard collects what the existing flow needs: organisation name, the
      **top administration unit name** (a place, e.g. country/region — for
      `/configure`), workspace address (subdomain) with **live availability
      check**, admin name, email, password, workspace language.
- [ ] Final step shows a "creating your workspace" → "check your email to
      activate" screen (activation preserved).
- [ ] After the activation link, the workspace is already configured from the
      wizard answers — the visitor lands in a usable control center, not an
      empty `/configure` form.
- [ ] A visitor can abandon and resume (answers persisted locally).

### Technical Acceptance Criteria
- [ ] The wizard reuses `POST /register`, `/register/activate` (via the email
      link) and `/register/configure`. No duplicate tenant-creation logic.
- [ ] Turnstile enforced on the `register` submission exactly as today (no new
      unprotected write path).
- [ ] One new **read-only** endpoint only: subdomain availability (§4).
- [ ] No data-model change; no mobile/SQLite impact.
- [ ] Frontend passes eslint (curly, no-undefined, prefer-arrow-callback,
      prettier); backend passes `flake8`.

---

## 3. Data Model Changes

**None.** A completed onboarding is a new `Tenant` + its superadmin, already
visible in the platform console (`admin/tenants/summary`,
`admin/tenants/:id/users` → Name + Email). That **is** the lead record.

### D-3 (carried): no lead model — the lead is the tenant + superadmin

A new `OnboardingLead` table/endpoint to re-store the registrant's identity is
speculative complexity (YAGNI): the console already answers "who signed up, how
do we reach them". Structured `sector` / "what problem" is deferred; if ever
needed it gets a dedicated column/table (not `Tenant.features`, which is a
controlled entitlement enum). Sales qualifies over the superadmin's email.

---

## 4. API Contract

Introduces **no new write**. It sequences the existing MT-006 endpoints and adds
one read-only helper.

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| GET | `/api/v1/register/subdomain?value=<x>` | **New (read-only).** Live availability for the address step; returns `{available, reason}`. | Public |
| POST | `/api/v1/register` | **Existing.** Phase 1: tenant + superadmin; sends activation email. Turnstile enforced. | Public |
| POST | `/api/v1/register/activate` | **Existing.** Email activation gate. | Public (token) |
| POST | `/api/v1/register/configure` | **Existing.** Phase 2: level-0 + root admin; wizard pre-fills this. | Session |

**Subdomain availability (resolved from code, 2026-10-29):** no such endpoint
exists today; `POST /register` validates format (`RegexField`, min 3),
reserved/collision names (`host_collision_reason` + `self_service_reason` in
`utils.workspace_name`) and DB uniqueness (400 on collision). The new helper
runs the **same three checks** and creates nothing (~15 lines reusing the
validators). The final `register` POST stays authoritative (closes the TOCTOU
race).

### Configure pre-fill
After activation (session exists), the wizard's stored answers — the dedicated
top-unit/place name plus a default level-0 label (`"Country"`) — are POSTed to
`/register/configure` automatically, so the visitor never sees the raw form. On
failure, fall back to the existing `/configure` page (no regression).

---

## 5. Decision Log

### D-2: Wrap the two-phase flow; keep email activation
"Automatic tenant after the last step" is satisfied by auto-driving the
existing endpoints. The only visible pause is the activation email — the one
thing protecting against throwaway/typo'd addresses (the gap MT-006 closed). A
new instant-provision endpoint re-opens that hole and needs its own hardening,
so it is rejected. The wizard is UX over an unchanged backend.

### Seams to leave for [[LP-003]]
- **One onboarding container owns orchestration** — the wizard and the future
  AI chat are two drivers of the same "collect → provision" contract; the
  `register`/`configure` calls live behind that contract, not inside the
  wizard UI.
- **Provisioning is a function of collected answers**, callable from either
  driver (wizard = fixed fields; AI = plan-derived payload).

---

## 6. Compatibility & Migration
- [x] Existing `register`/`activate`/`configure` signatures unchanged.
- [x] Direct `/register` still works, indistinguishable from wizard-driven.
- [ ] Mobile: no impact. SQLite: no change.
- [x] Seeders/CLI unchanged.

---

## 7. Security Considerations
- [ ] Turnstile on the `register` submission exactly as today; the availability
      helper is read-only and rate-limited.
- [ ] No new lead store → nothing new can block tenant creation.
- [ ] No new attack vector on tenant isolation — the wizard only creates the
      visitor's own tenant via the existing guarded flow.

---

## 8. Testing Strategy

| Test | Coverage |
|------|----------|
| Unit (backend) | Availability endpoint: taken / free / invalid. |
| Unit (frontend) | Wizard step machine (Back/Next, resume from localStorage); availability states; validation mirrors backend rules. |
| Integration | Wizard → `register` → "check email"; post-activation auto-`configure` → control center; auto-configure failure falls back to `/configure` (`HTTP_HOST` override per CLAUDE.md). |

---

## 9. Open Questions
- [x] **Root-unit name for `/configure`** — RESOLVED: add **one dedicated wizard
      question** for the top administration unit — a *place* (e.g. the country
      or region name). The organisation name is **not** reused for it, because
      the root unit is a place ("Kenya"), not an org ("Rural Water Trust"), and
      MT-006's configure form names a real top unit. The **level-0 label**
      defaults to a generic (`"Country"`) the admin can rename later in
      manage-levels, so the wizard stays short (one place question, not two).

---

## 10. References
- [[LP-001]] (landing page this plugs into), [[LP-003]] (AI onboarding reusing
  the same container/contract).
- `MT-006-two-phase-registration.md`, `MT-029-signup-and-auth-abuse-hardening.md`.
- Code: `frontend/src/pages/login/components/Register.jsx`,
  `backend/api/v1/v1_users/views.py` + `urls.py` + `serializers.py`,
  `backend/api/v1/v1_users/utils/workspace_name.py` (validators).
- Prototype: the wizard demo in `LP-001-landing-design-brief.md` (port to React).
- **Live prototype (for review):** <https://claude.ai/artifact/FzcaWS4DNkPuVj3hmxHyZh>
  — open the wizard via "Preview the wizard". ⚠️ Keep this link private
  (restricted via the artifact's Share menu).

---

## 11. Task Breakdown · **~8h**

Estimates assume agentic coding + porting the prototype wizard; tests folded
into each task's Tech AC. All tasks ≤8h.

**B1 · Subdomain availability endpoint — 1.5h**
- User AC: address step shows available / taken / invalid live.
- Tech AC: `GET /register/subdomain` reusing `host_collision_reason` +
  `self_service_reason` + `Tenant.exists`; creates nothing; unit tests
  (taken/free/invalid).

**B2 · Wizard container + step state machine (port demo) — 2h**
- User AC: one question/screen, Back/Next, progress; resume after reload.
- Tech AC: port prototype wizard JS to React; `localStorage` try/catch;
  keyboard-navigable; owns the "collect → provision" contract (seam for LP-003).

**B3 · Wizard step screens + validation + Turnstile — 2h**
- User AC: collects required fields with inline validation.
- Tech AC: validation mirrors backend (subdomain regex/min-3, email, Django
  password rules); Turnstile widget rendered; state-machine unit tests.

**B4 · Wire wizard → `POST /register` + "check your email" — 1.5h**
- User AC: finishing creates the tenant and shows an activation-pending screen.
- Tech AC: sends `captcha_token`; maps 400 (subdomain/email taken) to the right
  step; no duplicate logic; integration test of the happy path.

**B5 · Post-activation auto-configure (+ fallback) — 1h**
- User AC: after the email link, the user lands in a usable control center, not
  the raw configure form.
- Tech AC: on activated session `POST /register/configure` from stored answers;
  fallback to `/configure`; clears the wizard draft.

**Total: ~8h.**

**Dependencies:** B1 → B3; B2 → B3 → B4 → B5.

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-11-11 | Approved |
| Tech Lead | | | |
| Product | | | |
