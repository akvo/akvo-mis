# Feature Design Document: AI Layer for Visualisations (Architecture & Roadmap)

**Task ID**: VIZ-AI-001  
**Issue**: [#452](https://github.com/akvo/akvo-mis/issues/452)  
**Branch**: `epic/452-viz-ai-dashboard-visualization-layer`  
**Feature Name**: AI Layer on the Visualisation Feature  
**Author**: Akvo Engineering Team  
**Date**: 2026-09-22  
**Status**: Approved  
**Task Prefix**: `VIZ-AI-<Sequence>`  

---

## 1. Context & Problem Statement

```
Currently:
- Creating a dashboard in Akvo MIS requires manual composition: authors must manually select each widget type, form source, question binding, aggregation mode, grouping, color scheme, and grid column spans.
- Domain non-experts often struggle to choose the most effective visualization (e.g. Map for geolocation vs Bar for high-cardinality categorical data vs Line for temporal trends).
- Starting from a blank canvas is intimidating and slow when an author simply wants standard insights from a newly registered form family.
- Akvo MIS already has OPENAI_API_KEY configured in settings (used by api/v1/v1_chatbot).

Goal:
- Provide an AI Layer for the Dashboard Visualisation system that accelerates dashboard authoring across two core capabilities:
  1. Dashboard-Level Recommendation: Recommending a cohesive starter layout of complementary widgets based on a selected form family.
  2. In-Canvas Widget Suggestions: Recommending relevant next widgets while editing a dashboard, based on available form questions and already placed widgets.
- Enforce strict multi-tenant data privacy: Send ONLY form/question metadata and schema structures to the LLM (zero raw submission data / PII).
- Provide a robust rule-based deterministic fallback when the API key is unset or external calls are unavailable.
- Structure implementation into progressive task sequences, each with its own detailed design spec.
```

## 2. Requirements & Acceptance Criteria

### 2.1. User Acceptance Criteria (UAC)
- [ ] **Starter Generation**: When creating a new dashboard for a selected form family, authors can generate a complete starter layout of complementary widgets with one click.
- [ ] **Contextual Suggestions**: While editing a dashboard, authors can view ranked recommendations for next widgets based on unvisualized form questions and existing widgets.
- [ ] **1-Click Canvas Placement**: Authors can add any recommended widget directly to the canvas without manual configuration errors.
- [ ] **Actionable Insights**: Every suggestion includes a descriptive title and a 1-sentence rationale explaining the analytical insight.
- [ ] **Zero Disruption / Offline Fallback**: Authors never experience UI freezes or broken states if AI services or API keys are unavailable (deterministic heuristic fallback).
- [ ] **Tenant Isolation**: Authors cannot see or suggest visualizations from forms outside their assigned tenant workspace.

### 2.2. Technical Acceptance Criteria (TAC)
- [ ] **Zero-PII Transmission**: Only structural schema metadata (Form names, question labels, question types, option choices) is transmitted to external LLMs; zero individual submissions or GPS answers are sent.
- [ ] **Strict Tenant Scoping**: All form and dashboard resolutions are strictly filtered through `Forms.objects.for_user(request.user)` and `Dashboard.objects.for_user(request.user)`.
- [ ] **100% Wire Schema Parity**: All suggested widget payloads strictly conform to `DashboardWidgetSerializer` and pass `validate_dashboard_payload` without client-side key translation.
- [ ] **Deterministic Offline Fallback**: An internal rule-based engine generates valid widget recommendations when `OPENAI_API_KEY` is missing or external calls fail/time out.
- [ ] **Referential Integrity**: All suggested `form` and `question` IDs are validated against the active form family (`serialize_sources`), pruning hallucinations.
- [ ] **Test Coverage**: Minimum 80% automated test coverage across new backend endpoints and frontend components.

---

## 3. Core Capabilities

### 3.1. Capability A: Dashboard-Level Starter Recommendation
When an author initiates a new dashboard for a selected Root Form (and its monitoring children), the AI layer inspects the form family structure and produces a comprehensive starter dashboard layout consisting of:
- High-level metric summary KPIs.
- Categorical and status distribution charts (Pie/Bar).
- Temporal monitoring trends over time (Line).
- Geographic distribution maps (where coordinate questions exist).
- Recommended layout spans (`col_span`) and descriptive titles.

### 3.2. Capability B: In-Canvas Widget Suggestions
While actively editing a dashboard in the Dashboard Builder:
- The author can request context-aware widget recommendations.
- The AI layer evaluates remaining/unvisualized questions in the form family alongside existing widgets.
- Suggestions are presented in an interactive drawer with clear rationales, allowing authors to preview and add widgets directly onto the canvas with one click.

---

## 4. High-Level Architecture & Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Author as Dashboard Author
    participant FE as React Dashboard Builder
    participant BE as Django API (/manage/dashboards/ai/...)
    participant Fallback as Deterministic Heuristic Engine
    participant OpenAI as OpenAI API (gpt-4o-mini)

    alt Dashboard-Level Starter Generation
        Author->>FE: Selects Root Form + clicks "Generate AI Dashboard"
        FE->>BE: POST /api/v1/manage/dashboards/ai/suggest-dashboard { root_form_id }
        BE->>BE: Extract Form Family Metadata (Questions, Types, Options)
        alt OpenAI API Key Available
            BE->>OpenAI: Prompt (Form Metadata Schema + Output Schema)
            OpenAI-->>BE: Structured Dashboard Layout (Widgets + ColSpans + Titles)
        else OpenAI Unavailable / Fallback
            BE->>Fallback: Heuristic Layout Generator
            Fallback-->>BE: Deterministic Starter Layout
        end
        BE->>BE: Validate Referential Integrity (Form & Question IDs)
        BE-->>FE: 200 OK { name, description, widgets }
        FE->>Author: Populate / Preview Starter Dashboard
    else In-Canvas Widget Suggestions
        Author->>FE: Clicks "Suggest Widgets" in Builder
        FE->>BE: POST /api/v1/manage/dashboards/{id}/ai/suggest-widgets { existing_widgets }
        BE->>BE: Extract Unused / Complementary Questions
        BE->>OpenAI: Prompt (Remaining questions + Context)
        OpenAI-->>BE: Ranked Widget Candidates with Rationale
        BE-->>FE: 200 OK { suggestions }
        FE->>Author: Display Suggestion Drawer (1-Click Add)
    end
```

---

## 5. Privacy & Multi-Tenancy Boundary Principles 🛡️

> [!IMPORTANT]
> **Zero-PII / Zero-Raw Data Transmission Rule**:
> 1. **No Submission Data / PII**: Individual submissions (`Answers`, `FormData`, free-text responses, specific GPS coordinates of respondents) are **never** transmitted to external LLMs.
> 2. **Structural Schema Only**: Prompts receive exclusively structural metadata:
>    - Form names and Form types (`registration`, `monitoring`).
>    - Question labels and types (`number`, `option`, `multiple_option`, `date`, `autofield`).
>    - Option choice labels (e.g. `["Functioning", "Needs Repair", "Decommissioned"]`).
> 3. **Tenant Isolation**: All form and dashboard resolutions are strictly scoped through `Forms.objects.for_user(request.user)` and `Dashboard.objects.for_user(request.user)`.

---

## 6. Technology Strategy & Schema Parity Matrix

- **Primary Engine**: OpenAI `gpt-4o-mini` with JSON Schema Structured Outputs, utilizing the existing project `settings.OPENAI_API_KEY`.
- **Deterministic Heuristic Fallback**: An internal rule-based recommendation engine that generates valid chart configurations from question types if external AI services are unreachable or unconfigured.
- **Architectural & Quality Safeguards**:
  1. **24-Column Grid Normalization**: Layout rows are automatically balanced into standard multiples (KPIs: 6/12, Charts: 8/12, Maps/Tables: 24) preventing ragged gaps.
  2. **Multi-Lingual Parity**: System prompt instructs the model to match the natural language of the form schema for widget titles and rationales.
  3. **High-Cardinality Token Defense**: Option lists in metadata prompts are capped at top 15 choices to minimize input tokens and latency.
  4. **Visual Diversity Rule**: Prompts and heuristics enforce complementary chart distributions (max 2 of any single chart type; balanced mix of KPI, categorical, temporal/geo, and table).
  5. **Registration-Only Form Guardrail**: For forms without monitoring children, `measure` is forced to `null` and Table widgets are omitted.
  6. **Collision-Proof Temp IDs**: Frontend creates unsaved canvas widgets using `-Date.now() - index` avoiding state collision.
- **Payload & Schema Parity**: All suggested widget objects are contract-identical to `DashboardWidgetSerializer`, `builderConstants.js`, and `BuilderInspector.jsx`, using canonical keys:
  - `type`: `"kpi"` | `"bar"` | `"line"` | `"pie"` | `"table"` | `"map"` | `"scatter"`
  - `col_span`: integer (6, 8, 12, 24)
  - `title`: string (<= 255 chars)
  - `color`: string (<= 32 chars) | null
  - `form`: integer (valid form ID in family)
  - `question`: integer | null (valid question ID belonging to form)
  - `config`: object strictly matching widget defaults in `builderConstants.js` and validated by backend `validate_dashboard_payload` (e.g. `value_type`, `repeat_agg`, `group_by`, `stack_by`, `date_question_id`, `map_mode`, `color_scheme`, `columns`, `criteria`).
  - `rationale`: string (human-readable insight rationale).

Because the output shape matches `DashboardWidget` exactly, suggested widgets drop directly into the frontend `widgets` state array and save seamlessly via standard `PUT /manage/dashboards/{id}` with zero client-side translation or data loss.

---

## 7. Implementation Roadmap & Task Sequence (Max 3 Tasks)

The total estimated time for each task comprehensively includes **core implementation, automated test suites (TEA), manual testing/smoke verification during development, and code review**.

```
VIZ-AI-001 (Architecture & Roadmap Specification)
 ├── VIZ-AI-002: Backend AI Recommendation Engine & Suggestion Endpoints
 └── VIZ-AI-003: Frontend Dashboard Builder AI Integration & Verification
```

### Consolidated Task Breakdown:

| Task ID | Task Scope | Primary Touchpoints | Dev (Vibe Coding) | Testing (Auto + Manual) | Review & Polish | Total Est. | Detailed Spec File |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **VIZ-AI-001** | **Architecture & Roadmap Specification**<br>High-level system design, data boundaries, privacy rules, and task consolidation. | `doc/design/VIZ-AI-001-ai-dashboard-visualization-layer.md` | 30m | 15m | 15m | **1h** | Current Document |
| **VIZ-AI-002** | **Backend AI Recommendation Engine & Suggestion Endpoints**<br>Form family metadata extractor, OpenAI `gpt-4o-mini` structured prompt service, deterministic heuristic offline engine, `suggest-dashboard` & `suggest-widgets` endpoints, referential integrity filters, unit & integration test suite. | `backend/api/v1/v1_visualization/ai_prompts.py`<br>`backend/api/v1/v1_visualization/ai_service.py`<br>`backend/api/v1/v1_visualization/ai_heuristics.py`<br>`backend/api/v1/v1_visualization/dashboard_builder_views.py`<br>`backend/api/v1/v1_visualization/tests/test_ai_visualization.py` | 4.0h | 2.5h | 1.5h | **8h** | [VIZ-AI-002 Design Spec](file:///Users/galihpratama/Sites/akvo-mis/doc/design/VIZ-AI-002-backend-ai-recommendation-engine.md) |
| **VIZ-AI-003** | **Frontend Dashboard Builder AI Integration & Verification**<br>Dashboard AI client helper, Create Dashboard Modal AI starter generation, In-Canvas AI Suggestion Drawer, 1-click canvas insertion, error boundaries & fallbacks, Jest tests, manual smoke testing across forms, and docs sync. | `frontend/src/util/dashboardAi.js`<br>`frontend/src/pages/dashboards/CreateDashboardModal.jsx`<br>`frontend/src/pages/dashboards/AISuggestionDrawer.jsx`<br>`frontend/src/pages/dashboards/DashboardBuilder.jsx`<br>`frontend/src/pages/dashboards/BuilderPalette.jsx`<br>`frontend/src/pages/dashboards/__test__/` | 3.5h | 2.0h | 1.5h | **7h** | [VIZ-AI-003 Design Spec](file:///Users/galihpratama/Sites/akvo-mis/doc/design/VIZ-AI-003-frontend-dashboard-ai-integration.md) |
| **TOTAL** | **Full Feature Delivery** | **Backend + Frontend + Docs** | **8.0h** | **4.75h** | **3.25h** | **16h** | |
