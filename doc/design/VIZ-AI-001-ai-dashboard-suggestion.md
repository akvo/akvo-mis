# AI-assisted dashboard suggestion: design

**Its own epic — not part of the dashboard builder.** The dashboard-builder
epic is VIZ-001 through VIZ-009 and ends with a working tenant-authored
builder. This is `VIZ-AI-001`, unscheduled, and it is written now only
because it consumes the VIZ-001 §4 widget schema and could not have been
designed before that settled. Nothing in VIZ-002 … VIZ-009 depends on it or
needs to anticipate it. Picking it up later means reading this against the
code as built, not re-deriving it.

## Problem

The builder has a cold-start problem. A tenant who has just published their
first form opens an empty canvas and a vocabulary they have never seen —
measure, group by, stack by, include-unmonitored. The blank page is the hard
part; editing a draft someone else roughed out is easy.

It also answers the template question. The mockup's "start from a template"
flow cannot work across tenants, because question ids are tenant-local, so a
copied widget array binds to nothing (VIZ-001 §13.1). A suggestion generated
from *this tenant's own form definition* binds to their real question ids by
construction. That is a better answer than templates, not a substitute for
one.

This slice is additive and last. It produces VIZ-001 §4 config objects, so it
cannot be built before that schema is settled in code — which it is once
VIZ-005 and VIZ-006 have shipped.

## Decisions

- **Form structure is sent; tenant data is not.** The request carries a
  compacted definition of the form family — form names, question labels,
  types and option values. No `Answers` row, no `FormData`, no administration
  name, no user or submitter identity. A dashboard's design depends on the
  *shape* of the data, and all of that is in the definition.
- **Aggregate profiles are deferred.** Knowing that only two of five options
  are ever used, or that a numeric field ranges 0–3 rather than 0–3000, would
  let the model pick better chart types. That is an aggregate — option counts
  and min/median/max — not rows, and it is derivable from the query engine we
  already have. It is still a data-egress decision an NGO customer makes
  deliberately, so it is out of v1. **Raw answer rows are not sent at any
  tier.**
- **Off by default, per workspace.** Question labels are tenant content and
  can describe a programme, a population or a location. Sending them to a
  third-party API is the customer's decision, not ours.
- **The schema guarantees shape, not truth.** This is the important part. A
  structurally perfect widget can still reference a question that does not
  exist, bind a `group_by: option` chart to a `number` question, or set
  `measure: current_state` on a registration form. Nothing in a JSON schema
  catches any of that, so the output goes through **the same VIZ-005
  validators as a hand-built dashboard** — same code path, no exemption.
- **Nothing is persisted.** `suggest` is a pure function of its inputs: safe
  to call repeatedly, nothing to clean up if the tenant dislikes the result.

## Components

### 1. The endpoint

`POST /api/v1/manage/dashboards/suggest`, permission `dashboard_create`,
per-tenant rate limited.

Request: `root_form`, and an optional free-text `intent`
(*"Focus on which water points are currently broken and where."*).

Response: `name`, `description`, a widget array in the §4.1 shape with a
per-widget `rationale`, and `notes[]` listing what was dropped. Nothing is
written to the database.

```jsonc
// Request
{
  "root_form": 1749623934933,
  "intent": "Focus on which water points are currently broken and where."  // optional
}

// Response — nothing persisted
{
  "name": "Water Points Overview",
  "description": "Current operational status across all registered sites",
  "widgets": [ /* §4.1 shape, plus a per-widget `rationale` */ ],
  "notes": ["Dropped 1 suggested widget: question 9912 is not on this form."]
}
```

Each widget's `rationale` is one line ("counts sites whose latest visit
reported a breakage"), rendered beside it in the builder. The tenant is being
asked to review, so the reasoning has to be visible.

The suggested widgets are constrained to the requested form family (D-3) —
`root_form` and its monitoring children — because that is all the request
sends and all the validators accept.

### 2. What is sent

The compacted family definition, and nothing else:

```jsonc
{
  "root_form": {
    "id": 1749623934933, "name": "Water Points", "type": "registration",
    "questions": [
      {"id": 1749623934940, "label": "Water source type", "type": "option",
       "options": ["borehole", "spring", "piped"]}
    ]
  },
  "monitoring_forms": [
    {
      "id": 1749631041125, "name": "WP Monitoring",
      "questions": [
        {"id": 1749631041155, "label": "Operational status", "type": "option",
         "options": ["operational", "issue", "not_functional"]},
        {"id": 1749631041160, "label": "Date of visit", "type": "date"},
        {"id": 1749631041170, "label": "Litres per minute", "type": "number",
         "repeatable": true}
      ]
    }
  ]
}
```

Serialized deterministically — questions sorted by id,
`json.dumps(..., sort_keys=True)`. Non-deterministic serialization means two
identical forms produce two different byte strings and nothing ever caches.

**On sending values.** A dashboard's design depends on the *shape* of the
data, not its content — which question is the status question, which numeric
field is worth trending — and all of that is in the definition. Where values
would genuinely help is narrower: knowing that only two of five options are
ever used, or that a numeric field ranges 0–3 rather than 0–3000, would let
the model pick better chart types and thresholds. That is an aggregate
profile, not rows, and it is deferred (see Decisions).

### 3. Structured outputs

`client.messages.parse` with `output_format=SuggestedDashboard`, a static
Pydantic model built once at import:

```python
from pydantic import BaseModel, ConfigDict
from typing import Literal

class KpiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")   # → additionalProperties: false
    measure: Literal["current_state", "all_submissions"]
    option_value: str | None = None
    value_type: Literal["number", "percentage"] = "number"
    include_unmonitored: bool = False

class SuggestedWidget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["kpi", "bar", "line", "pie", "table", "map", "section_title"]
    title: str
    col_span: int
    form: int | None = None
    question: int | None = None
    config: KpiConfig | BarConfig | PieConfig | TableConfig | MapConfig | TextConfig
    rationale: str

class SuggestedDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    widgets: list[SuggestedWidget]


response = client.messages.parse(
    model="claude-opus-5",
    max_tokens=16000,
    system=[{
        "type": "text",
        "text": DASHBOARD_DESIGN_GUIDE,           # stable across every request
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": [
        {"type": "text", "text": form_definition_json,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": intent or "Suggest a general overview."},
    ]}],
    output_format=SuggestedDashboard,
)

if response.stop_reason == "refusal":
    raise SuggestionUnavailable(response.stop_details)
if response.stop_reason == "max_tokens":
    raise SuggestionTruncated()          # retry with a larger budget
suggestion = response.parsed_output      # a validated SuggestedDashboard
```

Three constraints shape those models:

- Every object needs `additionalProperties: false` — `extra="forbid"` on each
  model. Widget `config` is heterogeneous per type (§4.3), so it is a union
  of closed per-type objects.
- Numeric bounds are not supported in-schema. `col_span` cannot be
  constrained to 1–24 by the schema; the SDK strips such constraints and
  validates client-side. Our own validators are the real gate.
- Keep the schema static. A new schema pays a one-time compilation cost and
  is then cached for 24 hours, so it is built at import, never per-request
  from the tenant's form.

`stop_reason == "refusal"` and `== "max_tokens"` are handled explicitly
rather than falling through to a parse error.

### 4. Prompt caching

The design guide — widget vocabulary, the `measure` semantics, which question
types suit which chart — is identical for every tenant and every request. It
goes in `system` with a cache breakpoint; the form definition gets a second
breakpoint so repeat suggestions on the same form read both.

Rendering order is tools → system → messages, so the volatile part (`intent`)
comes **after** the form definition in the user turn. Two things silently
break this: interpolating a timestamp, request id or tenant name into the
system prompt, and non-deterministic serialization of the form. Claude Opus
5's minimum cacheable prefix is 512 tokens, so even a modest guide qualifies.
Verify with `usage.cache_read_input_tokens` — if it stays zero across
repeated calls, one of those two is present.

### 5. Model and governance

`claude-opus-5`, `max_tokens` generous enough to cover thinking plus output.
Effort starts at the default and sweeps down — this is schema-bound
generation, not long-horizon agentic work, and Opus 5 is unusually strong at
low and medium; measure before paying for more.

Credentials are platform-level: Akvo's API key, so the cost is a platform
cost, which is why the per-tenant rate limit is part of the endpoint rather
than an afterthought. A per-workspace toggle, default off, controls access.
Logging records the form id and the question-id list that was sent — enough
to audit what left, without duplicating it.

### 6. Frontend

In the builder, "Suggest widgets" calls the endpoint and drops the returned
widgets onto the canvas as **unsaved state**. The tenant edits and saves
through the normal `PUT`. Each widget's `rationale` renders beside it
("counts sites whose latest visit reported a breakage") — the tenant is being
asked to review, so the reasoning has to be visible. `notes[]` shows above
the canvas.

A suggestion therefore cannot reach a published dashboard without a human
pressing Save and then Publish.

## Data flow

    POST /manage/dashboards/suggest {root_form, intent?}
      → workspace toggle on?            no → 403
      → rate limit                      exceeded → 429
      → build family definition (structure only, sorted, stable)
      → messages.parse(system=guide⊕cache, user=[definition⊕cache, intent])
      → run every widget through the VIZ-005 validators
      → drop failures into notes[]
      → return; persist nothing
      → builder drops widgets on the canvas as unsaved state

## Error handling

- Workspace toggle off → 403. Rate limit exceeded → 429.
- `stop_reason == "refusal"` → 502 with a plain message; the builder stays
  usable and the tenant authors by hand.
- `stop_reason == "max_tokens"` → retried once with a larger budget, then a
  502.
- A widget that fails validation is **dropped and reported**, never silently
  accepted and never half-repaired. The model proposes; the validators
  decide.
- An upstream timeout or transport error surfaces as "suggestion
  unavailable". Nothing about the builder depends on this endpoint.

## Testing

- A response referencing a question not on the form is dropped and named in
  `notes`; a response with `measure: current_state` on a registration form
  is dropped.
- The suggestion path and the hand-built path call the same validator — one
  test asserts the shared code path, not two parallel implementations.
- Nothing is persisted: no `Dashboard` or `DashboardWidget` row exists after
  a call.
- Only structure is sent: assert the request body contains no answer value,
  administration name or user identity, for a fixture with data present.
- Repeated calls on the same form show a non-zero
  `usage.cache_read_input_tokens`.
- With the workspace toggle off, the endpoint returns 403 before any outbound
  request is made.
- Permission: a user without `dashboard_create` gets 403.

## Out of scope

- Aggregate data profiles (option counts, numeric ranges). Deferred behind
  the same per-workspace opt-in; raw rows never.
- Suggesting edits to an existing dashboard. This proposes a fresh array.
- Cross-family suggestions. One family per dashboard, permanently (D-3).
- Tenant-supplied API keys.

## References

- `doc/design/VIZ-001-dashboard-builder-data-architecture.md` — §4 widget
  config schema (what this endpoint must produce), §4.5 validation rules
  (the gate it runs through), D-3 (one form family), D-4 (`measure`)
- `doc/design/VIZ-005-dashboard-crud-api.md` — `validate_dashboard_payload()`,
  the validator this reuses rather than reimplements
- `doc/design/VIZ-006-dashboard-builder-ui.md` — the canvas a suggestion
  lands on as unsaved state
