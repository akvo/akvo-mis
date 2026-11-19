# Feature Design Document — Typeform-style Wizard Onboarding

> **Purpose**: Replace the landing CTA target (the bare `/register` form) with a
> pleasant, one-question-at-a-time wizard that wraps the **existing** two-phase
> registration and auto-configures the workspace. Second of three:
> **[[LP-001]]** landing · **LP-002 (this)** wizard · **[[LP-003]]** AI onboarding.

---

## Feature: Guided Wizard Onboarding (phase 1)

**Task ID**: LP-002
**Author**: Iwan Firmawan
**Date**: 2026-11-19 (rev. 3 — new `/onboarding` route; shared public shell extracted from the landing; `es` added MIS-wide; palette = platform blue `#1651b6` (D-4/D-5/D-10') · rev. 2 — inherits LP-001 design system + i18n + brand conventions)
**Status**: Review
**Estimate**: ~11h (AI-generated; hands-on = review + verify). Reuses LP-001's Tailwind setup; +shared shell + MIS-wide `es`.
**Depends on**: [[LP-001]] (landing page + CTA, Tailwind scoped setup, content layout, platform-blue palette)

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
- A Typeform-style wizard at a **new `/onboarding` route** (one question per
  screen, progress, Back/Next) that collects the same fields, creates the tenant
  through the EXISTING flow, and pre-fills `/configure` so the visitor lands in a
  usable control center after activation — never seeing the raw configure form.
- The landing CTA retargets from `/register` to `/onboarding`; direct `/register`
  stays as-is (unchanged, still works).
- No new provisioning path, no weakened email verification: the wizard is UX
  over an unchanged backend, plus one tiny read-only helper. The one backend
  change is additive: `es` joins the registration language choices (QC/D-10').
```

---

## 2. Requirements

### User Acceptance Criteria
- [ ] Clicking the landing CTA opens a step-by-step wizard at **`/onboarding`**
      (one question per screen, progress indicator, Back/Next), not a dense form.
      The wizard renders in the **same public shell as the landing** (shared
      header with brand + language switch), not the workspace app chrome (D-5).
- [ ] The wizard collects what the existing flow needs: organisation name, the
      **top administration unit name** (a place, e.g. country/region — for
      `/configure`), workspace address (subdomain) with **live availability
      check**, admin name, email, password, workspace language (en/es/fr).

> **`es` is in scope now (QC decision, D-10').** MIS ships en/fr today —
> `RegisterSerializer.language` is `ChoiceField(["en","fr"])`
> (`serializers.py:1212`). This work extends it to `["en","es","fr"]`, adds
> Español to the register/onboarding selector, and makes the app's `uiText`
> **fall back to en** for any missing `es` key so an `es` workspace never renders
> blank. A full `es` translation of the MIS UI can follow incrementally.
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
- [ ] **UI uses LP-001's scoped `#landing` Tailwind in the platform blue
      `#1651b6`** (D-8 + D-12 amendment), **not akvo green**; antd untouched; the
      wizard demo is the interaction reference, re-tinted to the blue tokens.
- [ ] **New `/onboarding` route**; the landing CTA (`hero.primaryCta.href`)
      retargets `/register` → `/onboarding`; direct `/register` unchanged.
- [ ] **Shared public shell** (D-5): the landing's header/footer are extracted
      into a reusable layout under `pages/landing/`; `/onboarding` renders in it,
      and the workspace app shell (antd `Layout.Header`, chatbot, tour) is
      suppressed on `/onboarding` — extending LP-001's `isLanding` guard (D-12).
- [ ] **`es` added MIS-wide** (D-10'): `RegisterSerializer.language` →
      `["en","es","fr"]`; Español in the register/onboarding selector; `uiText`
      falls back to `en` for missing `es` keys.
- [ ] **Wizard chrome (step prompts, labels, buttons) is per-locale JSON**
      (en/es/fr, English default/fallback) like [[LP-001]] §6, with the `{brand}`
      token for the product name. Values the user types are not translated.
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

### Design system & i18n (inherited from [[LP-001]])

The wizard is part of the landing surface, so it reuses LP-001's setup rather
than inventing its own:
- **Styling**: LP-001's scoped `#landing` Tailwind in the **platform Ant Design
  primary `#1651b6`** (D-8 + the D-12 blue amendment), **not akvo green** —
  primary / outline buttons, the `akvo*` blue tokens, Roboto Condensed /
  Assistant. No new Tailwind config; antd screens untouched. The prototype wizard
  is the layout/interaction reference, re-tinted to the blue tokens.
- **Content**: the wizard's static chrome (step prompts, field labels, button
  text, validation messages) lives in per-locale JSON like the landing
  (`content/en.json` + `es`/`fr`), **English default and fallback** (whole file
  or per key), with the `{brand}` token for the product name. The data the user
  enters (org, subdomain, email) is not translated.
- **Languages**: the workspace-language step offers en/es/fr; `es` is added
  MIS-wide as part of this work (D-10').

### D-4: New `/onboarding` route — retarget the CTA, don't replace `/register`

**Decision** (QA): the wizard is a **new route `/onboarding`**, not an in-place
replacement of `/register`. The landing CTA points to `/onboarding`; the bare
`/register` page stays untouched and keeps working (power users, email links,
and the wizard's own fallback all still reach it).

**Rationale**: a new route keeps the dense form as a safety net and a fallback
target for post-activation auto-configure failures (§4), and avoids coupling the
wizard's lifecycle to the existing form. One content value changes
(`hero.primaryCta.href` → `/onboarding`).

### D-5: Shared public shell extracted from the landing

**Decision** (QB): extract the landing's **header (brand + language switch) and
footer into a reusable public shell** under `pages/landing/`, and render both the
landing and `/onboarding` inside it. On `/onboarding` the workspace app shell
(antd `Layout.Header`, `ChatbotWidget`, `OnboardingTour`) is **suppressed**, the
same way the landing route does it (LP-001 D-12) — generalise `isLanding` to also
match `/onboarding` (e.g. an `isPublicShell` guard in `App.js`).

**Rationale**: the onboarding wizard should feel like one continuous public
surface with the landing, not jump into the workspace chrome. Extracting the
header/footer once avoids duplicating it and keeps the language switch consistent
across both. Presentation-only; no backend.

**Impact**: new `pages/landing/LandingShell.jsx` (or similar); `Landing.jsx`
consumes it instead of inlining the header/footer; `App.js` shell-suppression
guard widened to `/onboarding`.

### D-10': Add `es` to the registration language MIS-wide (supersedes the LP-001 D-10 "separate task")

**Decision** (QC): bring Español into the registration flow now, for wider reach.
`RegisterSerializer.language` → `ChoiceField(["en","es","fr"])`
(`serializers.py:1212`); add Español to the register/onboarding language
selector. **Safety requirement**: the app's `uiText` must **fall back to `en`**
for any missing `es` key, so a workspace created with `language="es"` never
renders blank screens before the full MIS `es` translation exists.

**Scope note**: the *minimum* here (accept `es`, offer it, don't break) is small;
a full `es` translation of the whole MIS UI is a larger, incremental effort and
is **not** blocking LP-002.

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
- Design system: the **akvo-web** repo (<https://github.com/akvo/akvo-web>),
  per [[LP-001]] D-8.
- `MT-006-two-phase-registration.md`, `MT-029-signup-and-auth-abuse-hardening.md`.
- Code: `frontend/src/pages/register/Register.jsx` (the existing form + language
  selector), `frontend/src/pages/landing/` (shell to extract), `App.js` (routes
  + shell-suppression guard), `backend/api/v1/v1_users/views.py` + `urls.py` +
  `serializers.py` (`language` choices at :1212),
  `backend/utils/workspace_name.py` (`host_collision_reason` /
  `self_service_reason` validators), `frontend/src/lib/ui-text.js` (`es` + en
  fallback).
- Prototype: the wizard demo in `LP-001-landing-design-brief.md` (port to React).
- **Live prototype (for review):** <https://claude.ai/artifact/FzcaWS4DNkPuVj3hmxHyZh>
  — open the wizard via "Preview the wizard". ⚠️ Keep this link private
  (restricted via the artifact's Share menu).

---

## 11. Task Breakdown · **~11h**

Estimates assume agentic coding + porting the prototype wizard; tests folded
into each task's Tech AC. All tasks ≤8h.

**B0 · Shared public shell + `/onboarding` route — 1.5h** (D-4, D-5)
- User AC: `/onboarding` shows the wizard in the same header/footer as the
  landing; the landing CTA opens it; `/register` still works directly.
- Tech AC: extract `pages/landing/LandingShell.jsx` (header + language switch +
  footer); `Landing.jsx` consumes it; add the `/onboarding` route and widen the
  `App.js` shell-suppression guard (`isLanding` → also `/onboarding`); retarget
  `hero.primaryCta.href`; eslint clean.

**B1 · Subdomain availability endpoint — 1.5h**
- User AC: address step shows available / taken / invalid live.
- Tech AC: `GET /register/subdomain` reusing `host_collision_reason` +
  `self_service_reason` + `Tenant.exists`; creates nothing; unit tests
  (taken/free/invalid).

**B2 · Wizard container + step state machine (port demo) — 2h**
- User AC: one question/screen, Back/Next, progress; resume after reload.
- Tech AC: wizard mounts at `/onboarding` inside the shared shell (B0); port
  prototype wizard JS to React; step transitions may reuse `framer-motion`
  (already in the tree from LP-001); `localStorage` try/catch; keyboard-navigable;
  owns the "collect → provision" contract (seam for LP-003).

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

**B6 · MIS-wide `es` (choices + selector + uiText fallback) — 1.5h** (D-10')
- User AC: a workspace can be created in Spanish; an `es` workspace never shows
  blank strings.
- Tech AC: `RegisterSerializer.language` → `["en","es","fr"]` (+ serializer
  test); Español in the register/onboarding selector; `uiText` resolves missing
  `es` keys to `en`; `flake8` + eslint clean. (Full `es` UI translation is a
  separate incremental effort, not in this task.)

**Total: ~11h.**

**Dependencies:** B0 → B2; B1 → B3; B2 → B3 → B4 → B5; B6 independent (backend +
selector), needed before the language step ships `es`.

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-11-11 | Approved |
| Tech Lead | | | |
| Product | | | |
