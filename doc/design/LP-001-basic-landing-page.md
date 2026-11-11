# Feature Design Document — Basic Landing Page

> **Purpose**: A public marketing landing page on the base domain that pitches
> Akvo MIS and funnels visitors into the **existing** self-service registration.
> This is the first of three split documents:
> **LP-001 (this)** landing page → existing sign-up · **[[LP-002]]** Typeform
> wizard · **[[LP-003]]** AI-assisted onboarding.

---

## Feature: Akvo MIS Public Landing Page (lead-gen funnel, phase 0)

**Task ID**: LP-001
**Author**: Iwan Firmawan
**Date**: 2026-11-11
**Status**: Review
**Estimate**: ~6h (agentic coding, porting the approved prototype)

---

## 1. Context & Problem Statement

```
Currently:
- The base domain (BASE_DOMAIN host) has NO marketing surface. The frontend
  has a `window.appConfig.showLandingPage` flag (App.js:181), but when true it
  renders the dashboard `<Home />`, not a landing page. Nothing pitches the
  product to an unauthenticated visitor.
- Self-service sign-up already works: the MT-006 two-phase registration
  (`/register` → email activation → `/configure`) is reachable on the base
  domain only (AUTH-003). It is a bare form — functional, not inviting.

Goal (this doc only):
- A public landing page on the base domain that sells the product in one
  scroll: welcome copy, a "free forever + paid for advanced" message, a
  Kobo / Akvo MIS / DHIS2 positioning table (Akvo MIS deliberately in the
  middle), and a single prominent CTA.
- The CTA funnels into the EXISTING registration flow (the current
  `Register.jsx`). No wizard, no new backend — that is LP-002.
```

### Scope boundary

| In scope (LP-001) | Out of scope (later) |
|-------------------|----------------------|
| Marketing landing page behind `showLandingPage` on the base domain | The Typeform wizard → **[[LP-002]]** |
| CTA links to the existing `/register` page | AI conversational onboarding → **[[LP-003]]** |
| Benchmark table, i18n (en/fr), light/dark, mobile | Any new backend endpoint or data model |

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A visitor on the base-domain root (`/`) sees a marketing page: headline,
      "free forever" message, benchmark table, and a primary **Try it yourself**
      CTA.
- [ ] The CTA takes the visitor to the existing registration page (`/register`).
- [ ] The page is bilingual (en/fr) with a language switch; copy is not
      hardcoded in one language.
- [ ] The page reads well on a phone (single column, no horizontal scroll) and
      supports light + dark.
- [ ] A secondary **Talk to our team** link is present for the paid/custom path.

### Technical Acceptance Criteria
- [ ] Landing renders only on the base-domain host and only when
      `showLandingPage` is true; subdomains unaffected.
- [ ] No new backend endpoint, no data-model change.
- [ ] Copy + benchmark rows are data/config (i18n), not scattered literals, so
      Akvo can edit without a code change where practical.
- [ ] Frontend passes `./dc.sh exec -T frontend npx eslint` (curly,
      no-undefined, prefer-arrow-callback, prettier).

### Non-Functional
- [ ] No heavy assets (benchmark table is HTML/CSS, not an image).
- [ ] Accessibility: semantic headings, the comparison is a real `<table>` with
      header scope, CTA is a real link, visible focus states, legible contrast
      in both themes.

---

## 3. Data Model Changes

**None.** No models, no migration. A completed sign-up is already a `Tenant` +
its superadmin, visible in the platform console — that is the lead record (see
[[LP-002]] §3 for the "no lead model" rationale, which this doc inherits).

---

## 4. API Contract

**No new endpoints.** The CTA is a link to the existing `/register` page, which
already drives `POST /register` → activation email → `/register/configure`
(Turnstile enforced, MT-029). Nothing on this page writes to the backend.

---

## 5. Decision Log

### D-1: Build a real `<Landing />` behind the existing `showLandingPage` flag

**Options**: (1) new marketing component rendered by `showLandingPage` at `/`;
(2) a separate static site outside the React app.

**Decision**: Option 1 — replace the `<Home />` currently shown behind
`showLandingPage` (App.js:181) with a dedicated `<Landing />`.

**Rationale**: The flag, base-domain gating and `/register` guard already
exist. A separate site duplicates i18n, theming, Turnstile and deployment.
Laziest correct path: one new component behind a flag already plumbed
`generate_config.py` → `config.js` → `App.js`.

**Impact**: `frontend/src/App.js` root route; new `pages/landing/`. No backend.

### D-5: Benchmark table is honest positioning, Akvo MIS in the middle

Present Kobo / Akvo MIS / DHIS2 as a complexity spectrum, not "Akvo wins every
row". Akvo sits between KoboToolbox (light survey tool) and DHIS2 (heavy
aggregate HIS). A dishonest all-green table is a credibility risk with the
technical buyers who become paid partners. Rows in §11.

### D-6: AI drafts the benchmark table at build time, not live in the page

The table is **AI-drafted from vendor feature pages + this codebase** (§11),
stored as reviewed config/i18n — **not** scraped live. Live scraping is fragile
and risky on our most public page (KoboToolbox returned HTTP 403 to automated
fetch; a live table could show a blank/stale competitor column, and rendering
unreviewed competitor claims is a credibility/legal hazard). Refresh = re-run
the same prompt periodically; a human skims before publishing.

### D-7: "Free forever" for the core + a paid tier for advanced needs

The page promises the **core platform is free forever** (the brief's "semua
fitur GRATIS!") **and** openly offers a **paid option for advanced
capabilities, custom solutions and long-term support**. True today — no
quota/billing/plan-limit code exists in the backend (checked 2026-10-29).

**Accepted consequences**: "core free forever" commits to unlimited free on
current features (infra/abuse cost on Akvo; anti-abuse is the only guard; hard
to walk back). The core/advanced boundary is a future product decision;
"advanced" means custom builds, support and future enterprise capability —
**not** today's existing features. No `features`/plan flag or billing model is
in scope here.

---

## 6. Type/Constant Mappings

None — this page stores nothing. Copy and benchmark rows live in i18n dicts.

---

## 7. Compatibility & Migration

- [x] Existing registration unaffected (CTA just links to it).
- [x] Single-host installs (`BASE_DOMAIN` empty, `showLandingPage` false) see no
      change — landing never renders.
- [ ] Mobile app: no impact (web-only).
- [x] Seeders/CLI unchanged.

---

## 8. Security Considerations

- [ ] **No new public write** — the page only links to the existing,
      Turnstile-protected `/register`. No new attack surface.
- [ ] **No secrets in landing config** — `showLandingPage`, copy and table rows
      are public; keep them in `config.js`/i18n, never mix tokens.

---

## 9. Testing Strategy

| Test | Coverage |
|------|----------|
| Unit (frontend) | Landing renders behind flag; i18n copy renders for en/fr; benchmark table semantics. |
| E2E / manual | Landing shows only on base domain + flag on; subdomain shows none; mobile viewport; CTA navigates to `/register`; light/dark. |

---

## 10. Open Questions

- [x] **Landing visual design** — RESOLVED: a Claude artifact HTML draft exists
      (`LP-001-landing-design-brief.md`), reviewed; port to React/antd at build.
      No Figma dependency for v1.
- [x] **Benchmark content** — AI-drafted with sources (§11, 2026-10-29).
      Remaining human task is a *skim* (esp. the Kobo row, whose page blocked
      automated fetch), per D-6.
- [x] **Free promise** — RESOLVED: "core free forever + paid for advanced"
      (D-7).

---

## 11. References

- `LP-001-landing-design-brief.md` — the design handoff prompt + the prototype.
- **Live prototype (for review):** <https://claude.ai/artifact/FzcaWS4DNkPuVj3hmxHyZh>
  — the interactive landing page, plus the wizard demo ([[LP-002]]) and the AI
  chat demo ([[LP-003]]). ⚠️ **Keep this link private** (restricted to the
  owner + invited reviewers via the artifact's Share menu); do not publish it
  openly.
- Related: `MT-006-two-phase-registration.md` (the sign-up the CTA funnels to),
  `MT-029-signup-and-auth-abuse-hardening.md` (Turnstile),
  `001_auth_subdomain_registration_spec.md` (base-domain `/register` guard).
- Code touchpoints: `frontend/src/App.js` (root route, `showLandingPage`),
  `backend/api/v1/v1_data/management/commands/generate_config.py`.
- Next docs: **[[LP-002]]** (wizard), **[[LP-003]]** (AI onboarding).

### Draft copy (tone reference — finalise + translate en/fr)

> **Welcome to Akvo MIS.** The powerful platform that manages your data with
> ease — and uses AI to turn it into visualisations, automatically. Curious?
> Come try it yourself. **Free forever.**
>
> CTA: **Try it yourself →** (goes to sign-up)

### Benchmark table (AI-drafted from live sources, 2026-10-29)

Drafted from the vendors' feature pages + Akvo MIS capabilities read from this
codebase. **Skim before publishing** — competitor pages change; Kobo's page
blocked automated fetch (its row leans on secondary sources).

| Capability | KoboToolbox | **Akvo MIS** | DHIS2 |
|---|---|---|---|
| Primary focus | Survey / field data collection | **Monitoring + management information across an org hierarchy** | National-scale aggregate + tracker HIS |
| Setup complexity | Low | **Medium** | High |
| Offline mobile collection | Yes (KoboCollect / Enketo) | **Yes (native app, local SQLite, background sync)** | Yes (Android app) |
| Field / question types | Rich (skip logic, repeats, geo point/line/polygon) | **16 types incl. cascade, entity, administration, geo, signature, autofield** | Configurable data elements, event/tracker |
| Multi-level org / geographic hierarchy | Limited | **Built-in, path-based, drives access control** | Strong (core design) |
| Monitoring over time (repeat visits on one datapoint) | Via repeat groups, manual | **First-class monitoring forms (parent → child)** | Longitudinal tracker |
| Dashboards / visualisation | Basic + Excel export | **Built-in dashboard builder: charts, maps, KPIs** | Powerful (pivot, charts, maps), steep |
| AI-assisted visualisation | No | **Yes (AI dashboard suggestions)** | ML forecasting via external CHAP |
| In-app AI assistant | No | **Yes (chatbot)** | No |
| Approval / review workflow | Validation + review | **Multi-level approval workflow** | Data approvals |
| Data export | Excel / CSV | **Excel / DOCX reports, XLSForm, export jobs** | Open API, SQL views, FHIR |
| Learning curve | Gentle | **Moderate** | Steep |
| Cost to start | Free Community Plan (nonprofits: ~5k submissions/mo, 1 GB) | **Free forever (core)** | Free & open source (self-host, high ops) |

> Positioning: Akvo MIS is the middle path — more structure and monitoring than
> a survey tool, far less operational weight than a full HIS.

**Sources**: DHIS2 — <https://dhis2.org/features/> (official, 2026-10-29).
KoboToolbox — <https://www.kobotoolbox.org/features/>,
<https://www.kobotoolbox.org/pricing/> (official; page blocked automated fetch,
corroborated via vendor pricing + third-party reviews). Akvo MIS — this repo.

---

## 12. Task Breakdown · **~6h** (high confidence — porting the prototype)

Estimates assume agentic coding + reuse of the approved prototype
(`LP-001-landing-design-brief.md`): porting HTML/CSS/JS to React, not redesign.

**A1 · Landing route + flag wiring — 1.5h**
- User AC: base-domain `/` shows the landing page; subdomains unaffected.
- Tech AC: `<Landing/>` behind `showLandingPage && onBaseDomain` in `App.js`;
  CTA links to `/register`; no authed/subdomain redirect regression.

**A2 · Port landing sections to React/antd (from prototype) — 3h**
- User AC: all sections render; phone-responsive; light/dark.
- Tech AC: transcribe prototype HTML/CSS into components; benchmark is a
  semantic `<table>`; eslint/prettier clean.

**A3 · i18n (en/fr) + hook to `store.language` — 1.5h**
- User AC: language switch flips all copy; defaults from tenant/store.
- Tech AC: strings in i18n dict (no literals); FR verified; no EN/FR leakage.

**Total: ~6h.** (Optional: Matomo CTA event ~1h.)

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-11-11 | Approved |
| Tech Lead | | | |
| Product | | | |
