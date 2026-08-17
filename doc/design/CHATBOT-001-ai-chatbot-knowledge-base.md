# AI Chatbot Knowledge Base — Feature Specification

**Feature ID**: CHATBOT-001
**Branch**: `feat/ai-chatbot-planning`
**Status**: Draft — Pending Manager Review
**Estimation Mode**: Vibe coding + manual test

---

## Overview

Build an in-app AI chatbot widget powered by **OpenAI Assistants API + Vector Store** that helps platform users navigate Akvo MIS features. The bot reads the current page URL to infer context, answers natural-language questions grounded in the platform's knowledge base, dynamically inherits tenant branding (colors & style), and floats over every authenticated page in the React frontend.

---

## 5W1H Analysis

| Dimension | Detail |
|-----------|--------|
| **Who** | Authenticated end-users of any Akvo MIS tenant (all roles) |
| **What** | Floating chat widget, backend proxy, RST-to-MD converter & vector ingestion pipeline |
| **Where** | Frontend: global overlay component with dynamic tenant branding. Backend: new Django app `api.v1.v1_chatbot` |
| **When** | Triggered by user clicking the chat FAB; KB converted to `.md` & indexed once at deploy + re-indexed on doc change |
| **Why** | Lower support friction during onboarding; users struggle to find relevant docs while inside complex pages (Form Builder, Approvals, etc.) |
| **How** | 1) `docs/source/*.rst` → `.md` files → OpenAI Vector Store. 2) Chat messages + current URL → backend proxy → OpenAI Assistants thread → response |

---

## Architecture Overview

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant FE as React Widget (Tenant Branded)
    participant BE as Django /api/v1/chatbot/
    participant OAI as OpenAI Assistants API

    U->>FE: Click chat FAB (any page)
    FE->>FE: Capture window.location.pathname & Tenant Theme
    U->>FE: Type question + send
    FE->>BE: POST /api/v1/chatbot/message/\n{message, page_url, thread_id?}
    BE->>OAI: Add message to thread\n(system context includes page_url → feature name map)
    OAI->>BE: Stream response chunks (SSE) / Polling response
    BE->>FE: Proxy SSE stream / JSON response
    FE->>U: Render markdown response with primary brand accents
```

### URL → Feature Context Map (Backend)

A simple dict in the backend translates `pathname` prefixes to friendly context strings injected into the system prompt:

| URL prefix | Context label |
|------------|--------------|
| `/form-builder` | "Form Builder" |
| `/manage-data` | "Data Management" |
| `/approvals` | "Approval Workflow" |
| `/master-data` | "Master Data Management" |
| `/users` or `/add-user` | "User Management" |
| `/roles` or `/add-role` | "Roles & Permissions" |
| `/dashboard` | "Dashboard" |
| `/mobile-assignment` | "Mobile Assignment" |
| `/downloads` | "Downloads & Exports" |
| `/settings` | "Settings" |
| *(anything else)* | "General Platform" |

---

## Phase 1 — Knowledge Base Ingestion Pipeline (RST + Supplementary MD ➔ Vector Store)

**Goal**: Convert all Sphinx RST documentation plus comprehensive supplementary Markdown guides (incorporating `akvo-react-form-editor` and `akvo-react-form`) into an OpenAI Vector Store.

### 1. Form Editor & Runtime Documentation Gap Resolution

The base Sphinx RST docs in `docs/source/` only cover high-level overviews. To ensure the AI chatbot can accurately answer granular "how-to" questions in the Form Builder (`/form-builder`) and Data Entry (`/forms`), we supplement the RST conversion with dedicated, comprehensive Markdown guides generated from `akvo-react-form-editor`, `akvo-react-form`, and Akvo MIS design specifications.

#### Supplementary Form Knowledge Documents (`docs/md/`)

| File | Topic & Scope | Source Basis |
|------|---------------|--------------|
| `akvo_react_form_editor_guide.md` | • **Editor Layout & Tabs**: Edit Form, Translations, Preview, JSON view.<br>• **Question Groups**: Creating, ordering, configuring repeatable groups.<br>• **Question Settings**: Label, variable name, tooltip, required flag, double entry validation, min/max bounds, prefixes/suffixes.<br>• **Skip Logic & Dependencies**: Single and multi-question condition rules (equals, not equals, greater/less, in list).<br>• **Cascade Setup**: Hierarchical cascade URL integration with tenant root administration. | `akvo-react-form-editor` (GitHub repo & RTD), `FormBuilderCreate.jsx`, `FormBuilderEdit.jsx` |
| `akvo_react_form_runtime_guide.md` | • **Webform Runtime**: Form filling lifecycle, progress tracking, section navigation.<br>• **All 16 Field Types**: Input, number, text, date, option, multiple_option, cascade, tree, table, autofield (computed logic), geo (point/trace/shape), entity, signature, attachment.<br>• **Validation & Drafts**: Required field checks (`onCompleteFailed`), draft autosaving (`saveDatapoint`), submission format. | `akvo-react-form` (GitHub repo & README), `Forms.jsx`, `ManageDraftForm.jsx` |
| `akvo_mis_form_lifecycle_guide.md` | • **Registration vs Monitoring**: Linking monitoring forms to registration parents (`parent_id`).<br>• **Form Versioning**: Draft staging, publish snapshot activation, historical submission immutability.<br>• **Permissions**: View, Create, Edit, Publish, Delete capabilities by role.<br>• **Import / Export**: JSON structure, tenant isolation rules during import. | Akvo MIS `FB-001` through `FB-015` specs, `docs/source/formBuilder.rst` |

### 2. Intermediate Markdown Generation (`docs/md/`)

The ingestion pipeline generates and consolidates clean Markdown files in `docs/md/`:
- **Sphinx RST Conversion**: 15 standard system docs (`start`, `install`, `administration`, `approval`, `dataManagement`, `MasterDataManagement`, `mobileApp`, etc.) converted to `.md` with Sphinx directives stripped.
- **Supplementary Guides**: Form Editor guide, Webform Runtime guide, and Form Lifecycle guide added to the knowledge set.

### 3. Ingestion Pipeline: `scripts/ingest_kb.py`

```
1. Convert all *.rst from docs/source/ to docs/md/
2. Bundle with supplementary guides (akvo_react_form_editor_guide.md, akvo_react_form_runtime_guide.md, etc.)
3. Split all Markdown files into semantic chunks (~500 tokens each with header breadcrumbs)
4. Upload .md files to OpenAI Files API
5. Create or update named Vector Store ("akvo-mis-kb") with file-search configuration
6. Output vector_store_id → persist to .env as OPENAI_VECTOR_STORE_ID
```

---

## Phase 2 — Backend: `api.v1.v1_chatbot`

### New Django App Structure

```
backend/api/v1/v1_chatbot/
├── __init__.py
├── apps.py
├── views.py            # ChatMessageView with SSE streaming / JSON
├── serializers.py      # ChatRequestSerializer
├── urls.py             # path("chatbot/", ...)
├── management/
│   └── commands/
│       └── ingest_kb.py   # Django management command
└── tests/
    └── test_chatbot.py
```

### New API Endpoint

**`POST /api/v1/chatbot/message/`** — requires JWT authentication

**Request:**
```json
{
  "message": "How do I add a question group?",
  "page_url": "/form-builder/123/edit",
  "thread_id": "thread_abc123"
}
```
> `thread_id` is optional — omit to start a new conversation thread.

**Response (SSE stream):**
```
data: {"delta": "To add a question group, "}
data: {"delta": "click Insert group here..."}
data: {"thread_id": "thread_abc123", "done": true}
```

### Backend Logic Flow

1. Validate JWT → `request.user` (tenant-scoped via existing middleware)
2. Map `page_url` → context label via `URL_CONTEXT_MAP`
3. Create or reuse OpenAI thread (`thread_id` from request)
4. Add user message with injected system context:
   > `"User is currently viewing: {context_label}. Answer based on the Akvo MIS documentation."`
5. Run the Assistant with `vector_store_id` file-search tool attached
6. Stream response chunks via `StreamingHttpResponse` + `text/event-stream`

### New Environment Variables

```bash
OPENAI_API_KEY=sk-...
OPENAI_ASSISTANT_ID=asst_...
OPENAI_VECTOR_STORE_ID=vs_...
```

### Requirements additions (`backend/requirements.txt`)

```
openai>=1.30.0
gevent>=22.10.0   # required for SSE streaming with gunicorn
```

### Django settings additions (`mis/settings.py`)

```python
OPENAI_API_KEY = environ.get("OPENAI_API_KEY", "")
OPENAI_ASSISTANT_ID = environ.get("OPENAI_ASSISTANT_ID", "")
OPENAI_VECTOR_STORE_ID = environ.get("OPENAI_VECTOR_STORE_ID", "")
```

---

## Phase 3 — Frontend: Tenant-Branded Chatbot Widget

### Multi-Tenant Brand & Style Awareness

The floating chat widget dynamically binds to the active tenant's brand configuration:
- **FAB & header accents**: Uses tenant CSS variables (e.g. `var(--primary-color)`)
- **Header badge**: Displays the bot persona name alongside the tenant logo/style
- **Message bubbles**: Accent colors follow tenant primary palette

### Component Structure

```
frontend/src/components/chatbot/
├── ChatbotWidget.jsx       # FAB + collapsible panel (tenant branded)
├── ChatbotMessages.jsx     # Message list with markdown rendering
├── ChatbotInput.jsx        # Text input + send button
└── chatbot.scss            # CSS with CSS variable tenant overrides
```

### UX Design

| Element | Behaviour |
|---------|-----------|
| **FAB** | Bottom-right fixed button, chat icon, tenant primary color |
| **Panel** | 380×520px slide-up card above FAB, glassmorphism consistent with Ant Design theme |
| **Context chip** | Small pill: e.g. `📍 Form Builder` — updates as user navigates |
| **Streaming** | Text renders token-by-token as SSE arrives |
| **Thread persistence** | `thread_id` stored in `sessionStorage` — clears on tab/browser close |
| **Persona header** | Bot name (e.g. *Mira*) shown in panel header |

### State Management

Local React `useState` + `useRef` only — no Redux/global store changes needed.

### New npm dependency

```
react-markdown   # render bot responses as Markdown
```

---

## Open Questions for Manager & Stakeholder Review

---

### 1. 🔁 Response Mode: Streaming (SSE) vs Polling

> [!IMPORTANT]
> This decision affects infrastructure configuration and user experience.

| Approach | Pros | Cons |
|----------|------|------|
| **Streaming (SSE + gevent)** | • Text streams token-by-token — best UX.<br>• Feels instant, no blank wait screen. | • Requires `gunicorn --worker-class gevent` update.<br>• Slightly higher memory per active streaming connection. |
| **Polling / JSON** | • Works with existing standard Gunicorn setup.<br>• Simpler implementation, no worker change. | • User waits 3–6s for full response before seeing anything.<br>• Worse onboarding experience — users feel the system is slow. |

**Recommendation**: **Streaming** — adding `gevent` to `requirements.txt` is low risk and yields significantly better UX.

---

### 2. 🤖 Bot Persona (MIS-Contextual Options)

> [!TIP]
> Persona options are scoped to the **Monitoring Information System** context. Grouped by personality archetype to help pick the right fit.

#### 🔵 Professional / Mission-Driven

| Name | Full Title | Tone |
|------|-----------|------|
| **Mira** | *Monitoring Intelligence & Response Assistant* | Calm, authoritative, precise. Reflects the monitoring DNA — ideal for org-wide deployments. ⭐ Recommended |
| **Vela** | *Verified Evidence & Learning Assistant* | Purposeful, evidence-focused. Suits programs where data verification and learning cycles matter. |
| **Trace** | *Tracking & Reporting Assistance for Connected Evidence* | Systematic, technical. Ideal for data-heavy users managing submissions and approval chains. |
| **Clarity** | *Your MIS Knowledge Companion* | Warm but precise. Emphasises cutting through complexity — great for new users during onboarding. |

#### 🟢 Field-Friendly / Human

| Name | Full Title | Tone |
|------|-----------|------|
| **Fieldhand** | *MIS Field Support* | Grounded, helpful, no-nonsense. Familiar to enumerators; suggests on-the-ground reliability. |
| **Scout** | *MIS Exploration & Support Guide* | Energetic, curious. Suggests scouting the platform for answers — suits mobile-first field users. |
| **Tally** | *Your MIS Count & Collect Companion* | Friendly, practical. References counting & data tally — relatable to form submission workflows. |
| **Akara** | *Akvo Knowledge & Response Assistant* | Warm, globally neutral name. "Akara" echoes "Akvo" and means "letter/script" in several languages. |

#### 🟣 Technical / Data-Centric

| Name | Full Title | Tone |
|------|-----------|------|
| **DataPoint** / **D.P.** | *Your MIS Data Guide* | Playful nod to the core unit of work — approachable for power users and form builders. |
| **Nexus** | *MIS Knowledge Hub* | Conveys connecting users to the right information across features and modules. |
| **Forma** | *Form & Data Assistant* | Form-building native — highly relevant to Form Builder and Submission users. |
| **Pulse** | *Real-Time Monitoring Intelligence* | Dynamic, modern. Suggests live data, active monitoring, and rapid response. |

#### 🟡 Navigation / Discovery

| Name | Full Title | Tone |
|------|-----------|------|
| **Atlas** | *Akvo MIS Navigation Guide* | Exploratory, knowledgeable. Helps users chart their way through platform features. |
| **Beacon** | *MIS Guidance & Support* | Reassuring, directional. A lighthouse guiding users through complex workflows. |
| **Quill** | *Your Form & Documentation Assistant* | Creative, detail-oriented. Suits content-heavy users — form designers, admins, data managers. |
| **Luma** | *Light Through Your MIS Journey* | Bright, approachable, optimistic. Great for onboarding-first contexts where user confidence matters. |

**Recommendation**: **Mira** for professional/multi-tenant deployments · **Scout** or **Luma** for onboarding-focused contexts.

---

### 3. 💰 OpenAI API Cost & Implementation Complexity

> [!IMPORTANT]
> **Development Complexity: Medium**
> Well-understood integration pattern. No custom ML/model training. Primary complexity is SSE streaming wiring between Django and React.

#### OpenAI Services & Pricing

| Service | Purpose | Pricing |
|---------|---------|---------|
| Files API | Upload RST/MD docs as searchable files | Free to upload |
| Vector Store | Store & search embedded KB chunks | $0.10 / GB / day |
| GPT-4o mini | Cost-efficient, sufficient for doc Q&A | $0.15 / 1M  input · $0.60 / 1M output tokens |
| GPT-4o | Higher quality answers (optional upgrade) | $2.50 / 1M input · $10.00 / 1M output tokens |

#### KB Storage Cost

| Item | Estimated Size | Monthly Cost |
|------|---------------|-------------|
| 17 RST docs as `.md` files | ~200 KB | < **$0.05 / month** |

#### Per-Message Token Estimate

| Component | Tokens |
|-----------|--------|
| System prompt + URL context | ~300 |
| Retrieved KB chunks (file-search) | ~1,500 |
| Conversation history (last 5 turns) | ~500 |
| **Total input tokens** | **~2,300** |
| Bot response (output) | ~400 tokens |

#### Monthly Running Cost by Usage Scale

| Scenario | Messages/Month | GPT-4o mini *(recommended)* | GPT-4o |
|----------|---------------|--------------------------|--------|
| **Small** — 20 users × 5 msgs/day | 3,000 | ~$1.20 | ~$19 |
| **Medium** — 50 users × 10 msgs/day | 15,000 | ~$6 | ~$95 |
| **Large** — 100 users × 20 msgs/day | 60,000 | ~$25 | ~$380 |

**Recommendation**: Start with **GPT-4o mini**. Quality is sufficient for documentation Q&A. Upgrade to GPT-4o only if answer quality is insufficient during testing.

---

### 4. 🔄 Knowledge Base Re-Indexing Strategy

> [!IMPORTANT]
> Decision needed: Who triggers re-indexing when docs are updated?

- **Option A — CI/CD Automated**: Re-run `ingest_kb` automatically whenever `docs/` files change on `main` push.
- **Option B — Manual Admin Command**: `python manage.py ingest_kb` during deployment releases.

---

### 5. 🛡️ Rate Limiting & Cost Controls

> [!IMPORTANT]
> Decision needed: How to cap OpenAI spend.

- **Option A — Per-User Daily Limit**: e.g. 30 messages/user/day.
- **Option B — Per-Tenant Monthly Cap**: Token budget per workspace.
- **Option C — Monitor First**: Watch usage via OpenAI dashboard for the first month, then set limits based on real data.

---

## Verification Plan (Manual Vibe Testing)

| # | Test Scenario | Expected Result |
|---|--------------|----------------|
| 1 | Run ingestion script → inspect `docs/md/` | Clean Markdown files, no RST directives |
| 2 | Switch tenant in frontend | FAB & widget accent colors update to tenant theme |
| 3 | On `/form-builder`, ask "How do I add a repeatable group?" | Response mentions gear icon + repeatable checkbox |
| 4 | On `/manage-data`, ask "How do I invite a new user?" | Correct answer, context from User Management docs |
| 5 | Ask follow-up referencing previous message | Thread context maintained correctly |
| 6 | Call `/api/v1/chatbot/message/` without JWT | 401 Unauthorized |
| 7 | Submit empty message | Validation error, no API call made |

---

## User Acceptance Criteria (UAC)

> [!IMPORTANT]
> These criteria define what the feature must achieve from the **user's perspective** to be accepted. All UAC must pass before the feature is considered shippable.

### UAC-1 — Chatbot Accessibility
- [ ] A floating chat button (FAB) is visible on every authenticated page of the platform.
- [ ] Clicking the FAB opens a chat panel without navigating away from the current page.
- [ ] The chat panel can be closed and re-opened without losing the current conversation.

### UAC-2 — Contextual Awareness
- [ ] The chat panel displays a context chip showing the current page/feature (e.g. `📍 Form Builder`).
- [ ] When asking a feature-specific question, the bot answers in the context of the page the user is on.
- [ ] When asking about a *different* feature while on another page, the bot still answers correctly without losing thread continuity.

### UAC-3 — Knowledge Base Quality
- [ ] The bot can correctly answer at least 80% of questions derived from the existing `docs/source/*.rst` documentation.
- [ ] The bot references steps, screenshots, or examples consistent with the actual platform UI.
- [ ] The bot does not fabricate features or steps that do not exist in the MIS platform.

### UAC-4 — Conversation Continuity
- [ ] Follow-up questions within the same session retain context from earlier messages.
- [ ] The conversation thread persists as the user navigates between pages within a session.
- [ ] Starting a new browser session starts a fresh conversation (no stale thread confusion).

### UAC-5 — Tenant Brand Consistency
- [ ] The chatbot widget accent colours match the active tenant's primary brand colour.
- [ ] The bot persona name (e.g. *Mira*) is displayed consistently in the panel header.

### UAC-6 — Security & Access
- [ ] The chatbot is only accessible to authenticated (logged-in) users.
- [ ] Unauthenticated access to the chat API returns a `401 Unauthorized` error.
- [ ] One tenant's users cannot access another tenant's conversation history.

---

## Technical Acceptance Criteria (TAC)

> [!IMPORTANT]
> These criteria define what must be true from a **technical/engineering perspective** before the feature is merged.

### TAC-1 — Backend API
- [ ] `POST /api/v1/chatbot/message/` requires a valid JWT and returns `401` without one.
- [ ] The endpoint validates required fields (`message`, `page_url`); returns `400` for missing/empty `message`.
- [ ] The URL context map covers all 10 platform page prefixes defined in the spec.
- [ ] OpenAI thread IDs are correctly created on first message and reused on subsequent messages in the same session.

### TAC-2 — Knowledge Base Ingestion
- [ ] `scripts/ingest_kb.py` successfully converts all 15 RST source files to Markdown under `docs/md/`.
- [ ] All `.md` files are uploaded to OpenAI Files API and attached to the named Vector Store (`akvo-mis-kb`).
- [ ] `OPENAI_VECTOR_STORE_ID` is written to `.env` after successful ingestion.
- [ ] Django management command `python manage.py ingest_kb` triggers the same pipeline without error.

### TAC-3 — Streaming / Response
- [ ] If streaming (SSE) is chosen: the Django backend returns a `StreamingHttpResponse` with `Content-Type: text/event-stream`.
- [ ] If polling is chosen: the endpoint returns a JSON response within 10 seconds under normal load.
- [ ] No unhandled exceptions are raised when the OpenAI API returns an error; the client receives a user-friendly error message.

### TAC-4 — Frontend Widget
- [ ] `<ChatbotWidget />` is mounted globally in `App.js` and only renders when the user is authenticated.
- [ ] The context chip updates in real-time when the user navigates between routes (no page reload required).
- [ ] `thread_id` is stored in `sessionStorage` and cleared on browser/tab close.
- [ ] Bot responses are rendered as Markdown (bold, lists, code blocks display correctly).
- [ ] The widget is fully keyboard-accessible (Tab to focus FAB, Enter to open/close, Enter to send message).

### TAC-5 — Code Quality
- [ ] All new backend code passes existing `flake8` linting rules.
- [ ] At minimum 3 unit tests are present for the `v1_chatbot` module:
  - `test_chatbot_requires_auth`
  - `test_chatbot_url_context_map`
  - `test_chatbot_serializer_validation`
- [ ] No new environment variables are hard-coded in source code; all use `environ.get(...)`.

### TAC-6 — Environment & Infrastructure
- [ ] `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID`, `OPENAI_VECTOR_STORE_ID` are documented in `env.example`.
- [ ] `docker-compose.override.yml` passes all three new env vars to the `backend` service.
- [ ] The `openai>=1.30.0` package is added to `backend/requirements.txt`.

---

## Files to Create / Modify

### New Files

| File | Description |
|------|-------------|
| `scripts/ingest_kb.py` | RST → MD converter + OpenAI Vector Store ingestion |
| `docs/md/` | Generated Markdown KB files (gitignored or committed) |
| `backend/api/v1/v1_chatbot/__init__.py` | App init |
| `backend/api/v1/v1_chatbot/apps.py` | AppConfig |
| `backend/api/v1/v1_chatbot/views.py` | `ChatMessageView` with SSE streaming |
| `backend/api/v1/v1_chatbot/serializers.py` | `ChatRequestSerializer` |
| `backend/api/v1/v1_chatbot/urls.py` | URL patterns |
| `backend/api/v1/v1_chatbot/management/commands/ingest_kb.py` | Management command |
| `backend/api/v1/v1_chatbot/tests/test_chatbot.py` | Unit tests |
| `frontend/src/components/chatbot/ChatbotWidget.jsx` | FAB + panel shell |
| `frontend/src/components/chatbot/ChatbotMessages.jsx` | Message list |
| `frontend/src/components/chatbot/ChatbotInput.jsx` | Input component |
| `frontend/src/components/chatbot/chatbot.scss` | Widget styles |

### Modified Files

| File | Change |
|------|--------|
| `backend/requirements.txt` | Add `openai>=1.30.0`, `gevent>=22.10.0` |
| `backend/mis/settings.py` | Add `v1_chatbot` to `API_APPS`, add 3 OpenAI env vars |
| `backend/mis/urls.py` | Add chatbot URL include |
| `frontend/src/App.js` | Mount `<ChatbotWidget />` inside authenticated layout |
| `frontend/src/components/index.js` | Export chatbot components |
| `.env` + `env.example` | Add `OPENAI_API_KEY`, `OPENAI_ASSISTANT_ID`, `OPENAI_VECTOR_STORE_ID` |
| `docker-compose.override.yml` | Pass OpenAI env vars to backend container |

---

## Estimation (Vibe Coding + Manual Test)

| # | Task | Min | Max | Confidence |
|---|------|-----|-----|-----------|
| 1 | RST-to-MD converter + `scripts/ingest_kb.py` | 2h | 3h | High |
| 2 | Run ingestion, verify Vector Store in OpenAI dashboard | 1h | 1.5h | High |
| 3 | Django app `v1_chatbot` + management command | 1h | 1.5h | High |
| 4 | `ChatMessageView` — validation + URL context map | 1h | 2h | High |
| 5 | OpenAI Assistants thread + SSE/JSON response handler | 2.5h | 4h | Medium |
| 6 | Backend unit tests (auth, context map, serializer) | 1h | 2h | High |
| 7 | `ChatbotWidget.jsx` with tenant brand binding | 1.5h | 2.5h | High |
| 8 | `ChatbotMessages.jsx` + `ChatbotInput.jsx` + Markdown | 1.5h | 2.5h | High |
| 9 | URL context chip + session-based thread management | 1h | 1.5h | High |
| 10 | `chatbot.scss` with tenant CSS variable overrides | 1h | 1.5h | High |
| 11 | End-to-end manual vibe test (7 scenarios) | 1h | 2h | High |
| 12 | `.env.example` + docker-compose env updates | 0.5h | 1h | High |
| **Total** | | **15h** | **25h** | |

> **Development complexity: Medium** — No custom ML training. Main risk is SSE streaming wiring (tasks 5 & 9 are the uncertainty band).
