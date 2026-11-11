# LP-001 — Landing Page Design Handoff Prompt

> Paste the block below into Claude (artifact / design) to generate the Akvo
> MIS landing page. It is self-contained. See `LP-001-basic-landing-page.md`
> for the landing spec, and `LP-002-*` / `LP-003-*` for the onboarding phases.

---

## PROMPT (copy from here)

You are designing a **public marketing landing page** for **Akvo MIS**, a Real
Time Monitoring Information System. Build it as a single, responsive,
production-quality web page (one screen-flow, scrollable sections). Output an
interactive HTML/CSS artifact I can preview.

### What Akvo MIS is
A platform that lets organisations collect field data (web + offline mobile),
structure it across a multi-level geographic/organisational hierarchy, run
monitoring over time, and visualise it in dashboards — now with **AI-assisted
data visualisation**. Think: the practical middle ground between a survey tool
and a full health-information system.

### The ONE job of this page
Turn a curious visitor into someone who clicks **"Try it yourself"** and starts
a free, self-service setup that creates their own workspace. It is a **lead
generator** toward long-term paid partnerships and custom solutions — so it
must feel credible to a technical/organisational buyer, not gimmicky.

### Tone & visual direction
- Modern, clean, confident **SaaS** aesthetic. Reference nuance from:
  `cadence-55bab1.webflow.io`, `muse.ai`, `rydoo.com` — generous whitespace,
  big confident headline, soft gradients/accents, rounded cards, subtle depth,
  real product/data imagery (dashboards, maps, charts), not clip-art.
- Friendly and inviting, but trustworthy. The hook is warmth + "it's free +
  try it now", not hype.
- **Light and dark mode** both first-class. Define colors as CSS tokens on
  `:root`, redefine for dark mode, give `body` an explicit background.
- **Mobile-first**: single column on phones, 16px side gutter, no horizontal
  scroll. The benchmark table must stay readable on a phone.
- Bilingual-ready (English + French). Write the copy in English; keep strings
  cleanly separated so a French version can drop in. Do not invent an
  Indonesian version.
- Accessibility: semantic headings, the comparison is a real `<table>` with
  header scope, CTAs are real buttons/links, visible focus states, legible
  contrast in both themes.

### Sections, in order

1. **Hero** — the emotional hook + primary CTA.
   - Headline (warm, confident). Working English copy:
     > **Welcome to Akvo MIS.** The powerful platform that manages your data
     > with ease — and uses AI to turn it into visualisations, automatically.
   - Subline: *Curious? Come try it yourself — everything here is free.*
   - Primary CTA button: **Try it yourself →** (this starts a guided setup
     that creates a workspace; treat it as the single most important element).
   - Secondary, quieter link: **Talk to our team** (for paid/custom — the
     lead-gen path).
   - Supporting visual: a clean product shot / dashboard mock on the side or
     below.

2. **"Everything is free" band** — a bold, unmissable strip emphasising that
   all features are free to start. Make it a confident statement, not fine
   print. (Short, one line + a reassuring sub-line.)

3. **How it works** — 3 simple steps that make self-service feel effortless:
   1) Answer a few questions (or drop a spreadsheet),
   2) We set up your workspace automatically,
   3) Start collecting and visualising your data.
   Icons + short labels. This previews the onboarding so the CTA feels safe.

4. **Why Akvo MIS (positioning)** — a short value row (3–4 cards): offline
   mobile collection, multi-level hierarchy + monitoring over time, built-in
   dashboards with AI-assisted visualisation, free to start.

5. **Comparison table** — the core trust element. Show **KoboToolbox vs Akvo
   MIS vs DHIS2**, positioning Akvo MIS deliberately **in the middle** of a
   complexity spectrum (more structured than a survey tool, far lighter than a
   full HIS). Make the **Akvo MIS column visually highlighted** (accent
   background / border). Honest, not all-green. Use these draft rows (mark them
   as to-be-fact-checked by the Akvo team):

   | Capability | KoboToolbox | **Akvo MIS** | DHIS2 |
   |---|---|---|---|
   | Primary focus | Survey / field data collection | **Monitoring + management information across an org hierarchy** | National-scale aggregate + tracker HIS |
   | Setup complexity | Low | **Medium** | High |
   | Offline mobile collection | Yes (KoboCollect / Enketo) | **Yes (native app, local storage, background sync)** | Yes (Android app) |
   | Multi-level org / geographic hierarchy | Limited | **Built-in, drives access control** | Strong (core design) |
   | Monitoring over time (repeat visits) | Via repeat groups, manual | **First-class monitoring forms** | Longitudinal tracker |
   | Dashboards / visualisation | Basic + Excel export | **Built-in builder: charts, maps, KPIs** | Powerful (pivot/charts/maps), steep |
   | AI-assisted visualisation | No | **Yes (AI dashboard suggestions)** | ML forecasting via external tool |
   | In-app AI assistant | No | **Yes (chatbot)** | No |
   | Approval / review workflow | Validation + review | **Multi-level approvals** | Data approvals |
   | Learning curve | Gentle | **Moderate** | Steep |
   | Cost to start | Free (nonprofit Community Plan) | **Free** | Free & open source (self-host, high ops) |

   Add a one-line caption under it: *Akvo MIS is the middle path — more
   structure and monitoring than a survey tool, far less operational weight
   than a full HIS.* (Rows drafted from vendor feature pages + the Akvo MIS
   codebase on 2026-10-29; present as current, keep the "pending review" note.)

6. **Lead-gen / partnership block** — soft pitch for organisations that want
   more: *"Ready to go further? We partner long-term and build custom
   solutions."* with a **Talk to our team** CTA. This is where paid intent is
   captured.

7. **Final CTA** — repeat **Try it yourself →** full-width, confident, with the
   "free" reassurance once more.

8. **Footer** — minimal: Akvo MIS, short links (docs, contact), language
   switch (EN/FR) placeholder.

### Hard constraints
- Do **not** fabricate customer logos, testimonials, fake reviews, or specific
  statistics. Use neutral placeholders clearly marked as placeholders.
- Keep all comparison claims defensible; label the table "draft — pending
  review".
- The **"Try it yourself"** CTA is the visual focal point of the page; every
  section should funnel toward it.
- One cohesive design system: a small color token set, one type scale,
  consistent spacing, consistent card/button styles across all sections.

Deliver the full responsive page as a previewable artifact, with light/dark
support and the comparison table working on mobile.

## PROMPT (copy to here)

---

### Notes for whoever runs this handoff
- The CTA leads into onboarding: the basic landing page (`LP-001`) funnels to
  the existing sign-up; the **guided wizard** is `LP-002` and the **AI setup**
  is `LP-003`. The designer doesn't build those flows — just the landing page
  and the entry buttons.
- Final copy must be translated EN/FR and fact-checked (comparison table rows,
  the "free" promise) before publishing — see `LP-001-basic-landing-page.md` §10.
- When it moves to build: landing lives behind the existing
  `window.appConfig.showLandingPage` flag on the base domain
  (`frontend/src/App.js`), replacing the current `<Home />` placeholder.
