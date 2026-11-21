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
**Date**: 2026-11-21 (rev. 7 — the global i18n library grew from per-page public
content to the **whole platform UI string set**: the `uiText` dictionary moved
into `lib/i18n/<locale>/ui.js` (JS, not JSON — values carry JSX/functions),
`es`/`fr` were translated, brand identifiers were extracted to
`lib/i18n/app-name.js`, the login/activate/configure funnel pages were wired to
it, and `RegisterSerializer.language` now accepts `es` — satisfying the D-10
prerequisite (D-16) · rev. 6 — header + footer extracted as the shared app shell for `/register` and `/find-workspace` (D-14): one fixed 70px bar everywhere, akvo-web-style scroll-progress bar, CTA hidden on register; landing content promoted to a global, locale-first, per-page i18n library at `lib/i18n/` and register/find-workspace made translatable through it (D-15) · rev. 5 — review feedback: `akvo-*` tokens renamed `brand-*` + all landing colours single-sourced in `lib/theme.js`; `<main>` landmark; a11y labels (close menu, flip card, phone alt, footer nav) moved to content JSON; language menu simplified to a disclosure with Escape-to-close; `useDocumentMeta` restores the previous title/description on unmount · rev. 4 — hero motion pass: scroll reveals, pointer-reactive dot grid, and a mobile↔dashboard flip card (D-13) · rev. 3 — as built: platform Ant Design primary `#1651b6` palette, interactive hero dashboard demo, standalone landing shell, `SHOW_LANDING_PAGE` gate removed · rev. 2 — akvo.org Tailwind design system + JSON content config + 3 default languages en/es/fr)
**Status**: Review
**Estimate**: ~4h (AI-generated; hands-on time is review + verify). Scope: Tailwind v3.4.3 scoped setup, JSON content config, akvo tokens, dark mode — see §12.

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
| Marketing landing page at `/` on the base domain (always on) | The Typeform wizard → **[[LP-002]]** |
| CTA links to the existing `/register` page | AI conversational onboarding → **[[LP-003]]** |
| Benchmark table, i18n (en/es/fr), light/dark, mobile | Any new backend endpoint or data model |

---

## 2. Requirements

### User Acceptance Criteria
- [ ] A visitor on the base-domain root (`/`) sees a marketing page: headline,
      "free forever" message, benchmark table, and a primary **Try it yourself**
      CTA.
- [ ] The CTA takes the visitor to the existing registration page (`/register`).
- [ ] The page is **trilingual (en / es / fr)** — akvo.org's default set — with
      a language switch (English, Español, Français); copy is not hardcoded in
      one language.
- [ ] The page reads well on a phone (single column, no horizontal scroll) and
      supports light + dark.
- [ ] A secondary **Talk to our team** link is present for the paid/custom path.
- [ ] The **site name, page title and meta description** are config, not
      literals — the brand name resolves from one source so a future rebrand
      (Akvo MIS → AMIS) is a config change, not a code edit (D-11).

### Technical Acceptance Criteria
- [ ] Landing always renders at `/` on the base-domain host **or** a single-host
      install (`BASE_DOMAIN` empty) — never on a tenant subdomain. Guard:
      `onBaseDomainHost()`. (The `SHOW_LANDING_PAGE` toggle was removed — Akvo
      MIS always ships a landing page.)
- [ ] No new backend endpoint, no data-model change.
- [ ] **All visible content** (copy, CTAs, how-it-works steps, cards, benchmark
      rows, footer links) comes from the **global i18n library**
      `frontend/src/lib/i18n/<locale>/<page>.json` — the `landing` namespace,
      read with `useTranslation("landing")`; English is the default/fallback — no
      copy hardcoded in components (D-15, which supersedes the D-9/§6 location).
      The register and find-workspace pages share the same library.
- [ ] **Styling uses akvo-web's scoped Tailwind setup**, re-tinted to the
      **platform Ant Design primary `#1651b6`** (`src/variables.scss $blue`), not
      akvo green — the app is antd-based, so the landing matches it: Tailwind
      v3.4.3 **scoped to `#landing`** (preflight off, `important: "#landing"`),
      tokens renamed `brand-*` with blue-scale values + `brand-bright #5B8DEF`
      for dark surfaces, all hexes in one source (`lib/theme.js`, imported by
      both the Tailwind config and the hero canvas/SVG); Ant Design screens
      untouched (D-8).
- [ ] **Standalone shell**: on the landing route the workspace app shell (antd
      `Layout.Header`, chatbot, onboarding tour) is suppressed, so the landing's
      own header (brand, language switch, CTA) is the only chrome (D-12).
- [ ] **Interactive hero dashboard demo**: the hero carries a product-shot card
      with sector tabs that switch stat tiles + an SVG trend chart; its copy and
      data live in `hero.demo` per locale (D-12, §6).
- [ ] **Compatible with the agreed prototype** (§11 link): same section set,
      order and interactions, re-tinted to the platform blue tokens/fonts.
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

**Amendment (2026-11-18):** the `SHOW_LANDING_PAGE` env toggle was removed
end-to-end (env, `settings.py`, `generate_config.py`, `appConfig`, App.js).
The landing now always renders on the base-domain host via `onBaseDomainHost()`,
since Akvo MIS ships a landing page by default. Single-host installs
(`BASE_DOMAIN` empty) now show it at `/` too.

**Rationale**: The flag, base-domain gating and `/register` guard already
exist. A separate site duplicates i18n, theming, Turnstile and deployment.
Laziest correct path: one new component behind a flag already plumbed
`generate_config.py` → `config.js` → `App.js`.

**Impact**: `frontend/src/App.js` root route; new `pages/landing/`. No backend.

### D-8: Style with akvo.org's Tailwind design system (scoped)

**Decision**: Build the page with akvo.org's Tailwind design system — the tokens
and component markup from **akvo-web** — using **Tailwind v3.4.3 scoped to
`#landing`** (`important: "#landing"`, `corePlugins.preflight: false`, a small
scoped reset in `landing.css`), the akvo tokens (`akvo #03AD8C`,
`akvo-deep #025F4D` hero, `akvo-light #E6F7F4`, `akvo-text #027A63`,
`akvo-border #56C8B2`, `text-*`, `bg-*`) and fonts (Roboto Condensed titles,
Assistant body).

**Rationale**: Reuses akvo.org's identity and component markup (hero band,
feature card, CTA banner, buttons) class-for-class; scoping keeps Ant Design 4
screens untouched; v3.4.3 runs on CRA 5 / Node 17.3 without ejecting. These
brand tokens are authoritative and supersede the generic palette in the design
brief.

**Compatibility with the prototype**: the agreed prototype (§11) stays the
**layout, section-order and interaction** reference (hero, free band,
how-it-works, two-ways, why, benchmark, partner, final CTA — the wizard/AI demos
belong to [[LP-002]]/[[LP-003]]). It is **re-tinted** to the akvo tokens/fonts:
the prototype's teal + display font become `akvo` green + Roboto Condensed /
Assistant. Same composition, akvo skin.

**Impact / net-new**: `frontend/tailwind.config.js`, `pages/landing/landing.css`,
fonts in `public/index.html`. **Dark mode is net-new** (akvo-web is light-only):
add `dark:` per element and a brighter accent for text on dark. Set
colours on headings directly (antd colours them); wide blocks use
`w-0 min-w-full overflow-x-auto`.

**Amendment (2026-11-18): palette = platform Ant Design primary, not akvo green.**
Most of the platform UI is Ant Design, whose primary is `#1651b6`
(`frontend/src/variables.scss $blue`). To keep the landing consistent with the
app it funnels into, the scoped Tailwind tokens carry the blue scale:
`brand #1651b6`, `brand-dark #114299` (hover), `brand-deep #0E2E6B` (hero band),
`brand-text #13448F` (text on white, 9:1), `brand-light #E7EEF9`,
`brand-border #A9C2EE`, plus `brand-bright #5B8DEF` for accents/text on dark
surfaces. This supersedes the green hexes above.

**Amendment (2026-11-19): tokens renamed `brand-*`, colours single-sourced.**
Review feedback: the `akvo-*` names now holding blue were misleading, so they
are renamed `brand-*` (the values are unchanged). All landing hexes — the token
scale plus the three colours the hero `<canvas>`/`<svg>` need (`brand-ink`,
`brand-frame`, `brand-chart`, `dotRgb`) and which can't be Tailwind classes —
now live in one CommonJS module, `frontend/src/lib/theme.js`, required by
`tailwind.config.js` and imported by `HeroDemo.jsx`/`HeroDotField.jsx`. It sits
in `lib/` (not under `landing/`) so other pages can adopt the design system
gradually, and under `src/` (not in the config) because CRA's ModuleScopePlugin
forbids component imports from outside `src/`. Change a colour there, once.

### D-9: All landing content from per-locale JSON files

**Decision**: Every section's copy, CTAs, steps, cards, benchmark rows and
footer links come from **per-locale JSON files** — `content/en.json`,
`es.json`, `fr.json` (one file per language, same structure); the `<Landing>`
component is presentation only. Schema + layout in §6.

**Rationale**: Translators edit one language file at a time (clean diffs, no
merge churn), the active locale can be lazy-loaded, and the benchmark table
(which Akvo must skim/refresh per D-6) is a data array, not markup. Per-category
splitting (`content/hero/en.json`, …) was rejected — 8 sections × 3 locales is
too many tiny files to keep in sync for one page (YAGNI); revisit only if the
content grows to many pages.

**Impact**: three JSON files + a tiny typed loader (fallback to `en.json`,
`{brand}` substitution); no backend.

### D-10: Three default languages (en / es / fr)

**Decision**: The landing page offers **English, Español and Français** — the
three languages akvo.org ships by default. Each locale is its own file (§6);
the switch lists all three. **English (`en`) is the default** — the initial
locale and the fallback for any missing key.

**Prerequisite (MIS-wide, related work)**: the registration handoff and the rest
of MIS support **en/fr only** today — `RegisterSerializer.language` is a
`ChoiceField(["en", "fr"])` (`backend/api/v1/v1_users/serializers.py:1213`) and
the selector lives in `frontend/src/pages/register/Register.jsx`. Adding `es`
means: extend that choice list to `["en","es","fr"]`, add Español to the
register selector, and supply `es` strings wherever MIS shows `fr`. This is
broader than the landing page (it extends MT-025) and should be tracked as its
own small task/PR — the landing switcher must not offer a language the
registration flow then rejects.

**Resolved (D-16, 2026-11-21)**: `RegisterSerializer.language` now accepts
`["en","es","fr"]`, and the MIS UI string set is translated es/fr through the
global i18n library — the switch can offer `es` safely.

**Impact**: the landing content JSON (en/es/fr) is self-contained; the MIS-wide
`es` addition is a dependency for the CTA → `/register` handoff and for
[[LP-002]]'s language step.

### D-11: Site name, title and description are config (rebrand-ready)

**Decision**: The brand name, the base-domain page `<title>` and the meta
description are **configuration, not literals**, so a future rebrand
**Akvo MIS → AMIS** is a config change, not a code edit.

- Brand name resolves from **one source**, `appConfig.name`
  (`generate_config.py`) — the same value the rest of MIS already uses. Rebrand
  = change that one value.
- Copy uses the `{brand}` token (§6) instead of writing "Akvo MIS", so headlines
  and the title update with the name.
- `site.title` / `site.description` live in the content JSON per locale.

**Rationale**: Akvo already treats the workspace site title as data (MT-026/
MT-030); the landing page follows the same principle for the base domain.

**Impact**: no component edits on rebrand; one config value + the content JSON.

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

### D-12: Standalone landing shell + interactive hero dashboard demo

**Decision** (as built, 2026-11-18): the landing is a **standalone marketing
surface**, not a page inside the workspace app frame.

- **Shell suppression**: on the landing route, `App.js` hides the workspace app
  shell — the antd `Layout.Header`, `ChatbotWidget` and `OnboardingTour` — so the
  landing's own header (brand, EN/ES/FR switch, CTA) is the only chrome.
  Guarded by the same `isLanding = pathname === "/" && onBaseDomainHost()`.
  Without this the antd header stacked on top and hid the language switch.
- **Interactive hero demo**: the hero is a two-column layout — copy + CTAs on one
  side, a product-shot dashboard card (`HeroDemo.jsx`) on the other. The card has
  sector tabs (Water & sanitation / Health facilities / Agriculture / Schools)
  that switch two stat tiles and an inline **SVG trend chart** (no chart library —
  pure geometry). Its text and numbers are config: `hero.demo` per locale (§6),
  so it stays editable and translates with the switch.

**Rationale**: the prototype's hero always carried an interactive product shot;
dropping it left the hero flat, and the stacked antd header buried the language
switch. Both are presentation-only — no backend, no new dependency.

**Impact**: `pages/landing/HeroDemo.jsx` (new), two-column hero in `Landing.jsx`,
`hero.demo` added to `content/{en,es,fr}.json`, three `App.js` shell guards.

### D-13: Hero motion pass + mobile↔dashboard flip card (as-built polish)

**Decision** (as built, 2026-11-18): add a scroll-motion layer and turn the hero
product shot into a flip card so the page feels alive. This is **polish beyond
the base LP-001 scope** (§12 A0–A4) — presentation-only, one new dependency, no
backend.

- **Dependency**: `framer-motion@6.5.1` (last v6; v7+ needs React 18, this app is
  17). Currently in the **main bundle** — lazy-splitting the landing is a
  follow-up so the app pages don't load it.
- **Scroll reveals**: `Reveal` fades + rises sections into view and replays on
  scroll up/down; `ScrollRevealText` reveals the how/why/benchmark headings
  word-by-word, each word settling at full brand colour.
- **Pointer-reactive hero backdrop**: `HeroDotField` draws a dot grid on a single
  `<canvas>`; dots near the cursor brighten and grow (rAF paused off-screen).
- **Flip card** (`HeroShowcase`): front `HeroMobile` — the mobile app's
  offline-sync walkthrough as an optimised **GIF** (`mobile-sync.gif`, morphed
  from the mobile-sync source frames via ImageMagick + gifsicle; only the GIF and
  the final still `mobile-sync-7.png` (the reduced-motion fallback) are kept —
  re-export the frames to retune) in a 3D-tilted, gently floating phone frame;
  back `HeroDemo` — the interactive
  dashboard. **Auto-flips** front↔back, with a **click-to-flip** button and
  **hover-pause** so the dashboard stays usable. Each face is `backface-hidden`
  with its own `rotateY` so the back reads un-mirrored.
- **Accessibility**: every effect honours `prefers-reduced-motion` (static, no
  animation); the flip collapses to just the static dashboard.

**Impact**: new `pages/landing/{Reveal,ScrollRevealText,HeroDotField,HeroShowcase,HeroMobile}.jsx`,
`framer-motion` dep, `public/assets/sprites/mobile-sync*`; `Landing.jsx` renders
`<HeroShowcase>`, a `<HeroDotField/>` hero backdrop, and wraps sections in
`<Reveal>`.

**Follow-up**: lazy-split the landing so framer-motion leaves the app bundle.

### D-14: Landing header + footer extracted as the shell for the base-domain public routes

**Decision** (2026-11-19): the landing header (brand + EN/ES/FR switch + CTA) and
footer are extracted to `pages/landing/LandingHeader.jsx` and
`pages/landing/LandingFooter.jsx` and reused as the app shell on the other
base-domain public routes — `/register` and `/find-workspace` — which previously
showed the generic workspace `Layout.Header` ("Replace with your organisation
logo" + Log in).

- **Shell-level mount**: `App.js` renders `<LandingHeader>` in place of
  `<Layout.Header>`, and `<LandingFooter>` after `Layout.Body`, for
  `publicShell = onBaseDomainHost() && pathname ∈ {/register, /find-workspace}`;
  it also suppresses the chatbot/tour there (same treatment as the landing).
  Mounting at the shell — not inside the page components — keeps the base-domain
  gate in one place, so a tenant subdomain hitting `/find-workspace` still gets
  the workspace header, not a double header.
- **Fixed 70px bar everywhere**: the header is a single `position: fixed`, 70px
  bar on every surface (landing, register, find-workspace) — no sticky/fixed
  variant. The `#login` pages reserve `$header-height` (86px) at the top for a
  fixed header, so the bar drops into that slot (~16px of body background shows
  below it, which reads as the page's own gutter).
- **Scroll progress** (akvo-web style): a primary-colour (`bg-brand`) bar along
  the header's bottom edge fills with scroll. The app scrolls `document.body`
  (not the viewport), so a capture-phase `scroll` listener reads the real
  `scrollTop` rather than `window.scrollY` / framer-motion's `useScroll` — no
  new dependency.
- **Scoping**: `LandingHeader`/`LandingFooter` render only `<header>`/`<footer>`
  (no `id`), so the caller places each inside an `id="landing"` element (Landing
  already is; `App.js` wraps the shell usages) — the `#landing *` reset never
  reaches the antd form.
- **Per-route CTA**: `showCta` hides the header button on `/register` (a "try it
  yourself" CTA there is self-referential); `/find-workspace` keeps it.

**Impact**: new `pages/landing/{LandingHeader,LandingFooter}.jsx`; `Landing.jsx`
renders `<LandingHeader/>`/`<LandingFooter/>` instead of inlining them; `App.js`
gains the `publicShell` branch; `pages/index.js` exports both. No change to
`Register.jsx`/`FindWorkspace.jsx`, no backend.

### D-15: Landing content promoted to a global i18n library (supersedes D-9 location)

**Decision** (2026-11-19): the landing content loader is promoted from
`pages/landing/content.js` to a **global i18n library** at
`frontend/src/lib/i18n/`, shared by every public base-domain page. Since the
shared header/footer (D-14) brought the register and find-workspace pages under
the same chrome and language switch, their hardcoded English copy was moved into
this library too, so they translate EN/ES/FR with the switch.

- **Engine**: `lib/i18n/index.js` holds the loader — `LANGS`, `resolveLang`,
  `brandName`, `getContent(namespace, code)` and the `useTranslation(namespace)`
  hook (re-renders on `store.language.active`). `store` is imported directly
  (`../store`), not via the `lib` barrel, so the module never pulls
  `geo.js → d3-scale` and stays Jest-loadable.
- **Translations, locale-first and per page**: `lib/i18n/<locale>/<page>.json`
  (e.g. `en/landing.json`, `es/register.json`). A translator opens one locale
  folder and sees every page; a new page adds one small file per locale plus one
  `BUNDLES` entry in `index.js` (static imports — no `require.context`, which
  Jest can't resolve). This replaces the single-growing-file approach and the
  per-locale landing files of D-9/§6.
- **Namespaces today**: `landing`, `register`, `findWorkspace`. `{brand}`
  substitution and en-fallback (whole-namespace and per-key) are unchanged from
  D-9; a parity test (`lib/i18n/__test__`) asserts es/fr match en per page.
- **Prerequisite (D-10) — now resolved (D-16)**: the landing/switch offers `es`
  and the MIS-wide registration flow accepts it —
  `RegisterSerializer.language` is `["en","es","fr"]` and the register
  workspace-language Select gained its Español option. The UI-locale switch
  (this library) is independent of that data-language field.

**Impact**: new `lib/i18n/` (engine + `{en,es,fr}/{landing,register,find-workspace}.json`
+ test); `pages/landing/content.js` and `content/` removed; the three landing
components, `Register.jsx` and `FindWorkspace.jsx` read via `useTranslation`.

### D-16: Platform UI strings join the global i18n library; funnel pages go es/fr

**Decision** (2026-11-21): the global i18n library (D-15) now also holds the
**whole platform UI string set**, not just the public per-page JSON namespaces.
The large `uiText` dictionary that the authenticated app renders from — menus,
buttons, table headers, every antd screen's copy — moved out of the monolithic
`lib/ui-text.js` and into the library at `lib/i18n/<locale>/ui.js`, and the
login → activate → configure **funnel** the landing CTA feeds into was wired to
it and translated es/fr. This is the D-10 prerequisite landing: the switch may
now offer `es` without the registration flow rejecting it.

- **Format — JS, not JSON.** The public page namespaces are JSON, but `uiText`
  values include React/JSX fragments and functions (e.g. `downloadAppText`,
  count-interpolating strings), which JSON can't carry — so these three files
  stay `.js`. `lib/i18n/ui.js` assembles them as
  `{ en, es: {...en, ...es}, fr: {...en, ...fr} }`, so `en` is the per-key
  fallback and a missing translation renders English rather than `undefined`.
- **`lib/ui-text.js` is now a re-export shim** of `./i18n/ui` — every existing
  `import { uiText } from "../lib"` keeps working, no call-site churn.
- **Brand identifiers extracted** to `lib/i18n/app-name.js` (`appName`,
  `apkName`), which imports nothing, so the JSX-eager `en/ui.js` can read them
  without a circular import / TDZ crash at module load. `brandName()` in
  `index.js` stays a **live** `window.appConfig` read (a test or a late
  `config.js` is reflected); `app-name.js` captures its value at import.
- **Funnel pages wired + translated**: `login/` (LoginForm, ResetForm),
  `activate/` and `configure/` read `uiText[language.active]` via a `useMemo`
  on `store.language.active`; their previously-hardcoded English strings became
  `uiText` keys with es/fr values. Dead keys (~80, zero references) were pruned
  from `en/ui.js` in the same pass.
- **D-10 prerequisite satisfied**: `RegisterSerializer.language` is now
  `ChoiceField(["en","es","fr"])`
  (`backend/api/v1/v1_users/serializers.py`) — the one backend line D-10/D-15
  flagged — and the workspace-language Select on `Register.jsx` gained its
  **Español** option to match. The UI-locale switch is independent of that
  data-language field; both now cover en/es/fr.

**Rationale**: once the shared shell (D-14) and the switch put register,
find-workspace and the landing under one EN/ES/FR control, leaving the rest of
the app English-only made the switch half-functional — flipping to Español on
the landing dropped back to English the moment the CTA opened the real app.
Moving `uiText` into the same library (rather than a parallel mechanism) keeps
one locale source and one switch. Presentation + one serializer line; no new
dependency, no data-model change.

**Impact**: `lib/i18n/{app-name.js, ui.js, en/ui.js, es/ui.js, fr/ui.js}` (new);
`lib/ui-text.js` reduced to a shim; `login/`, `activate/`, `configure/` pages
wired; `serializers.py` choice extended; `ui-text.test.js` + snapshot assert
en/es/fr.

---

## 6. Content Configuration (JSON)

> **Superseded by D-15**: the content system described below has moved from
> `pages/landing/content/` to the global `frontend/src/lib/i18n/` library, now
> split **locale-first and per page** (`lib/i18n/<locale>/<page>.json`) and
> shared by the register and find-workspace pages. The shape, `{brand}` token
> and en-fallback rules below still hold for the `landing` namespace
> (`lib/i18n/<locale>/landing.json`); read it with `useTranslation("landing")`.

All visible text, links and benchmark rows come from **per-locale JSON files** —
one file per language, same structure — so content is edited without touching
components (D-9):

```
frontend/src/pages/landing/content/
  en.json   ← source of truth for keys + fallback
  es.json
  fr.json
```

**Each file *is* a locale**, so strings are plain (no `{en,es,fr}` wrapper). The
loader imports `content/${store.language}.json` and falls back to `en.json`
**both** when that locale file is missing/fails to load entirely **and**
per-key for anything it lacks. English is always present and is the default.
Shape (abridged — `en.json`; sections render in this order):

```json
{
  "site": {
    "name": null,
    "title": "{brand} — real-time monitoring",
    "description": "…"
  },
  "hero": {
    "badge": "Free forever",
    "title": "Welcome to {brand}.",
    "lead": "…",
    "primaryCta":   { "label": "Try it yourself →", "href": "/register" },
    "secondaryCta": { "label": "Talk to our team", "href": "…" },
    "demo": {
      "brandLabel": "akvo", "liveLabel": "live", "syncedLabel": "synced",
      "demoBadge": "demo", "caption": "…",
      "chartTitle": "…", "chartNote": "…",
      "sectors": [
        { "name": "…", "metricLabel": "…", "metricValue": "1,284",
          "metricNote": "…", "rateLabel": "…", "rateValue": "92%",
          "rateNote": "…", "mapNote": "…", "trend": [40, 44, 42, 50, 58, 62, 70] }
      ]
    }
  },
  "freeBand":   { "title": "…", "body": "…" },
  "howItWorks": { "heading": "…", "steps": [ { "title": "…", "body": "…" } ] },
  "why":        { "heading": "…", "subtitle": "…",
                  "cards": [ { "icon": "offline", "title": "…", "body": "…" } ] },
  "benchmark":  {
    "heading": "…", "caption": "…",
    "columns": [
      { "key": "capability" },
      { "key": "kobo",  "label": "KoboToolbox" },
      { "key": "akvo",  "label": "Akvo MIS", "highlight": true },
      { "key": "dhis2", "label": "DHIS2" }
    ],
    "rows": [ { "capability": "…", "kobo": "…", "akvo": "…", "dhis2": "…" } ]
  },
  "partner":  { "title": "…", "body": "…", "cta": { "label": "…", "href": "…" } },
  "finalCta": { "title": "…", "body": "…", "cta": { "label": "…", "href": "/register" } },
  "footer":   { "links": [ { "label": "…", "href": "…" } ] }
}
```

`es.json` and `fr.json` mirror this tree with translated **text only** — the
non-text keys (`href`, `key`, `icon`, `highlight`) stay identical.

Rules:
- **Brand name = one source.** `site.name: null` means "use `appConfig.name`"
  (`generate_config.py`) — the single app-wide brand knob. A future rebrand
  **Akvo MIS → AMIS** is that one value changed; set a literal `site.name` only
  to override the brand on the landing alone (D-11).
- **`{brand}` token.** Any string may contain `{brand}`; the loader replaces it
  with the resolved name, so copy never hardcodes "Akvo MIS".
- `site.title` / `site.description` set the base-domain `<title>` and meta
  description.
- `icon` is a key into a small fixed icon set (`offline`, `hierarchy`, `ai`,
  `free`) — never markup. `highlight: true` marks the Akvo MIS column.
- No HTML in strings; the component owns all markup and Tailwind classes.
- **`en.json` is authoritative and always present.** A missing key, a missing
  section, or an **absent/unparseable locale file** all fall back to `en.json`
  (the whole file for an absent locale, per-key otherwise). A tiny unit test
  asserts `es.json`/`fr.json` have the same key paths as `en.json` (catches
  translation drift — the one cost of the per-locale split).

---

## 7. Compatibility & Migration

- [x] Existing registration unaffected (CTA just links to it).
- [ ] Single-host installs (`BASE_DOMAIN` empty) now show the landing at `/`
      (the `SHOW_LANDING_PAGE` gate was removed; this is an intentional change).
- [ ] Mobile app: no impact (web-only).
- [x] Seeders/CLI unchanged.

---

## 8. Security Considerations

- [ ] **No new public write** — the page only links to the existing,
      Turnstile-protected `/register`. No new attack surface.
- [ ] **No secrets in landing config** — copy and table rows are public; keep
      them in the content JSON, never mix tokens.

---

## 9. Testing Strategy

| Test | Coverage |
|------|----------|
| Unit (frontend) | `lib/i18n/__test__` — `getContent`/`useTranslation` read from `lib/i18n/<locale>/<page>.json` (en default; missing key → en); `es`/`fr` key paths match `en` **per page** (landing, register, findWorkspace); `{brand}` resolves from `appConfig.name`. |
| Unit (frontend) | `lib/__test__/ui-text.test.js` — the platform `uiText` dictionary exposes `en`/`es`/`fr`, each locale merged over `en` so a missing key falls back to English (D-16); snapshot guards the assembled shape. The funnel pages (login/activate/configure) render their copy from it. |
| Styling / scoping | Tailwind classes apply only inside `#landing`; **antd screens visually unchanged** (spot-check a control page); light + dark. |
| E2E / manual | Landing shows on the base-domain host (and single-host installs); tenant subdomain shows none; mobile viewport (table scrolls, no page widening); CTA navigates to `/register`. |

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
- Design system (tokens + component markup): the **akvo-web** repo
  (<https://github.com/akvo/akvo-web>) — tokens in `frontend/src/app/globals.css`,
  components in `frontend/src/components/`. Live: <https://akvo-web.akvotest.org/>.
- Related: `MT-006-two-phase-registration.md` (the sign-up the CTA funnels to),
  `MT-029-signup-and-auth-abuse-hardening.md` (Turnstile),
  `001_auth_subdomain_registration_spec.md` (base-domain `/register` guard).
- Code touchpoints: `frontend/src/App.js` (root route, `onBaseDomainHost()` guard),
  `backend/api/v1/v1_data/management/commands/generate_config.py`,
  `backend/mis/settings.py` and `env.example` (`SHOW_LANDING_PAGE` removed).
- Next docs: **[[LP-002]]** (wizard), **[[LP-003]]** (AI onboarding).

### Draft copy (tone reference — finalise + translate en/es/fr)

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

## 12. Task Breakdown · **~4h** (AI-generated; hands-on = review + verify)

Everything below is generated by AI from the agreed prototype (§11) and
akvo.org's Tailwind system (akvo-web); the hours are human review/verify, not
typing.

**A0 · Tailwind v3.4.3 scoped setup — 1h**
- Tech AC: pin `tailwindcss@3.4.3`; `tailwind.config.js` (content = landing,
  `important:"#landing"`, preflight off, akvo tokens + fonts); `landing.css`
  scoped reset; fonts in `public/index.html`; antd screens visually unchanged.

**A1 · Landing route + flag wiring — 0.5h**
- User AC: base-domain `/` shows the landing page; subdomains unaffected.
- Tech AC: `<Landing/>` at `/` guarded by `onBaseDomainHost()`; CTA → `/register`;
  no authed/subdomain redirect regression.

**A2 · Build sections in the platform-blue tokens (from the prototype) — 1.5h**
- User AC: all sections render; phone-responsive; same composition as the
  prototype, in the platform `#1651b6` colours; the hero's interactive dashboard
  demo switches on sector tap.
- Tech AC: hero (two-column + `HeroDemo.jsx` with SVG trend chart) / free / how /
  why / benchmark / partner / final / footer from akvo-web parts; benchmark
  `w-0 min-w-full overflow-x-auto`; headings carry their own colour; the
  workspace app shell is suppressed on the landing route (D-12);
  eslint/prettier clean.

**A3 · Global i18n library + loader (en/es/fr, brand token) — 0.5h** (as built, D-15)
- User AC: editing `lib/i18n/<locale>/<page>.json` changes copy without code; the
  switch flips locale (English/Español/Français, English default); the brand name
  comes from one config value (rebrand-ready).
- Tech AC: `useTranslation(ns)` / `getContent(ns, code)` merge the locale over
  `en` (per-key fallback), replace `{brand}` with `appConfig.name`, and set
  `<title>`/meta from `landing.site`; per-page key-parity test; no copy in JSX.
  Shared by landing, register and find-workspace. (MIS-wide `es` in the register
  choices is a separate task — D-10.)

**A4 · Dark-mode pass (net-new) — 0.5h**
- User AC: readable and on-brand in dark.
- Tech AC: per-element `dark:` classes; brighter blue (`akvo-bright #5B8DEF`) for
  text on dark; body background token.

**Total: ~4h.** (Optional: Matomo CTA event ~0.5h.)

**Dependencies:** A0 → A2; A1 independent; A2 → A3 → A4.

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | Iwan Firmawan | 2026-11-11 | Approved |
| Tech Lead | | | |
| Product | | | |
