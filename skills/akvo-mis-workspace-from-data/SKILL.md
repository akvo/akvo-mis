---
name: akvo-mis-workspace-from-data
description: Use when someone wants to stand up an Akvo MIS workspace or instance (such as who.mis.akvo.org or who.mis.akvotest.org) from an Excel or CSV file — for a PoC, demo or pilot. Also covers designing MIS forms, monitoring forms or the administration hierarchy from spreadsheet data, creating a new MIS tenant, and loading existing records into Akvo MIS through its API.
---

# Akvo MIS workspace from a spreadsheet

## Overview

A data team hands you a spreadsheet and wants a working Akvo MIS workspace
built from it. (*Datapoint* here means one registered thing, such as a school
or a water point, as in MIS. Never call it an "entity": MIS's `Entity`
model is a different, deprecated concept.) That means three things:
- an administration hierarchy,
- registration and monitoring forms,
- the existing records loaded in.

You analyse the data and propose the design **in plain language**. Once they
approve it, you create the workspace and seed it through the HTTP API.

**Core rule:** nothing is written to a server until the user has approved the
rendered plan (`plan.md`) and confirmed the workspace address and email. A
workspace can't be deleted through the API, and a wrong subdomain or form
stays behind.

Files in this skill:
- `scripts/profile_data.py`
- `scripts/render_plan.py`
- `scripts/mis.py`: stdlib HTTP; pandas is needed to read data.
- `reference/api.md`: endpoints and gotchas.
- `reference/plan-format.md`: the `plan.json` contract.

Read both references before writing a plan.

## Workflow

1. **Profile.** Run `python scripts/profile_data.py <files> --json profile.json`, then look at the data yourself too. The profiler proposes:
   - column types,
   - registration keys (ID columns whose rows repeat, i.e. one datapoint observed many times),
   - links between sheets,
   - place columns that nest,
   - lat/lng columns,
   - spelling variants.

   Ask what the team wants to **monitor** only when the data doesn't make it clear.
2. **Design.** Map the data onto MIS using the modelling rules below. Write `plan.json` (see the format reference) next to copies of the data files. Then:
   - Run `python scripts/render_plan.py plan.json`. Fix every PROBLEM it prints, by editing the plan or adding `aliases`, `value_maps` or `date_format`, until it prints `plan checks: OK`.
   - Run `python scripts/mis.py --plan plan.json load-data --dry-run`. This works offline, before any workspace exists. Read `load-report.csv`: every warning is an answer that would be dropped. Resolve each one, or list it as a caveat.
3. **Review with the user (gate 1).** Show them the content of `plan.md`: the tree, the question tables, the column mapping and a short "Decisions and caveats" list. Never show them the JSON. Ask them to approve it or change it, and iterate.
4. **Workspace details (gate 2).** Ask for:
   - their **email**,
   - the **subdomain**,
   - their first and last name,
   - the **environment**. Default to `mis.akvotest.org` for a PoC. Use `mis.akvo.org` (production) only if they explicitly say so.

   Then run `mis.py --plan plan.json check`. If the subdomain is taken or routing is missing, stop and ask.
5. **Choose who runs it.** Offer two options:
   - **(a) You run it:** needs network access from where you are. `check` tells you.
   - **(b) They run it on their machine:** give them the folder (plan.json, data, scripts) and the exact commands.

   Claude.ai and Desktop sandboxes often block outbound traffic, so fall back to (b) there.
6. **Register.** Run `mis.py register`. It generates a **temporary password**, prints it and emails an activation link. Tell the user:
   - "Click the link in the email from Akvo MIS (check spam). If a *Configure workspace* page opens, leave it unfilled. I set that up from the plan. Tell me when you've clicked it."
7. **Build (after they confirm the click).** Run `mis.py apply`.
   - It runs, in order: login → configure → seed-admin → seed-forms → load-data → status.
   - Every step is idempotent. After a failure, fix the cause and re-run `apply`.
   - Compare the final counts with the row counts in `plan.md`.
8. **Hand over.** Give them:
   - the URL,
   - the temporary password, with a request to change it via *Forgot password* on the login page,
   - the counts per form,
   - the rows that were skipped or failed (from `load-report.csv`),
   - what was deliberately not loaded,
   - next steps: invite users, assign mobile data collectors, build dashboards.

   Tell them `mis-state.json` holds the password and token, and not to share it.

## Modelling rules

| Signal in the data | MIS design |
|---|---|
| One row per datapoint (facility, household, school), with a stable ID | **Registration form**. The ID column becomes `key_columns` and a `meta` question. |
| The same ID repeats with dates or visits | Registration form for the columns that stay constant per ID, plus a **monitoring form** (`parent`) for the columns that vary |
| A flat survey with no repeats | A single registration form |
| Place columns where each child has exactly one parent (region → district) | **Administration levels**, root = the country or programme area |
| A place column with hundreds of free-text spellings | An `input` question, not an administration level |
| A column with 2–15 distinct categories | `option`; `a; b` cells are `multiple_option` |
| Lat/lng columns or "lat, lng" text | One `geo` question |
| Totals, percentages, formulas, derived columns | **Don't load them.** List them under `unmapped_columns` and suggest a dashboard later. Charts can only aggregate `number` answers. |
| The date an observation was made | Keep it as a `date` question. MIS stamps every record with the upload time and can't backdate. |
| Names, phone numbers, ID numbers of people (the profiler flags them as `PERSONAL DATA?`) | Ask the user before loading them (privacy) |
| Dates like `03/04/2026` (flagged as *ambiguous*) | Ask the user which order is right, then set `date_format` on the data spec. Ambiguous dates are refused otherwise. |
| Placeholder text such as `None`, `N/A`, `-` or `unknown` | Decide whether it is a real answer (add it as an option) or no answer. For no answer, map it to `""` in `value_maps`. |

Other rules:
- Only mark a question `required` if the data never leaves it blank. Otherwise every blank row produces a warning.
- Set number min/max generously around the observed range.
- You may fill in missing parent levels from general knowledge, for example district → region. Label them *inferred* in `notes` and have the user confirm them.
- Real-world caveats you notice go in `notes`: out-of-area coordinates, outdated admin names, suspicious values. Examples: "Kenya uses counties since 2013", "coordinates don't match the district".

## Common mistakes

| Mistake | Fix |
|---|---|
| Showing JSON as the proposal | The user reviews `plan.md`, which `render_plan.py` generates |
| Registering before approval, or on production by default | Get both gates first. The default target is akvotest. |
| Expecting MIS to email a temporary password | MIS emails only an activation **link**. The password is the one `register` generated. |
| Linking monitoring rows by datapoint id | `mis.py` links them by the parent's deterministic uuid, taken from `key_columns` |
| Using the Excel bulk upload for monitoring data | It cannot link rows to parents and reports errors only by email. Use `mis.py load-data`. |
| Renaming options or question `name`s after loading | Stored answers keep the old values. Change the design before `apply`. |
| Adding a level after units exist | Levels can't be added once units exist, so decide all of them in the plan |
| `login` returns "not activated" | The user hasn't clicked the link yet. Use `resend-activation` if it is lost. |

Local testing against a docker stack: add `--connect http://localhost:8000`
and set `"base_domain": "app.local", "scheme": "http"`. The activation
email then appears in Mailpit at `localhost:8025`. Run `mis.py activate
<link-or-token>` in place of clicking it.
