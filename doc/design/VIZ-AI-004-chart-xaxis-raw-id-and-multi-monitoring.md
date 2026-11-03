# Feature Design Document: Chart X-Axis Raw ID Fix & Multi-Monitoring Form Isolation

**Task ID**: VIZ-AI-004
**Parent Epic**: [VIZ-AI-001 Architecture & Roadmap](file:///doc/design/VIZ-AI-001-ai-dashboard-visualization-layer.md)
**Related Specs**:
- [VIZ-AI-001 AI Dashboard Visualization Layer](file:///doc/design/VIZ-AI-001-ai-dashboard-visualization-layer.md) (Parent Architecture & Roadmap)
- [VIZ-AI-002 Backend AI Recommendation Engine](file:///doc/design/VIZ-AI-002-backend-ai-recommendation-engine.md) (Engine, Heuristics, Prompts, Sanitizer)
- [VIZ-AI-003 Frontend Dashboard AI Integration](file:///doc/design/VIZ-AI-003-frontend-dashboard-ai-integration.md) (Create Modal, Suggestion Drawer, Inspector)
- [VIZ-AI-001 Original Suggestion Design](file:///doc/design/VIZ-AI-001-ai-dashboard-suggestion.md) (Form Family Boundaries & Validator Parity)

**Issue**: [#567](https://github.com/akvo/akvo-mis/issues/567) (Related: [#452](https://github.com/akvo/akvo-mis/issues/452), [#457](https://github.com/akvo/akvo-mis/issues/457), [#464](https://github.com/akvo/akvo-mis/issues/464))
**Branch**: `feature/567-dashboard-viz-ai-chart-xaxis-raw-id`
**Feature Name**: Chart X-Axis Raw ID Resolution & Multi-Monitoring Form Isolation
**Author**: Akvo Engineering Team
**Date**: 2026-11-03
**Status**: Implemented & Verified (All tests passing)
**Estimated Effort**: **5.5h** (Dev: 2.5h | Automated Testing: 1.5h | QA & Review: 1.5h)

---

## 1. Context & Root Cause Analysis

In `VIZ-AI-001`, `VIZ-AI-002`, and `VIZ-AI-003`, Akvo MIS delivered an AI Layer for dashboard visualization consisting of:
- **Backend Service** (`ai_service.py`, `ai_prompts.py`, `ai_heuristics.py`): Extracting zero-PII form family schema metadata, querying OpenAI `gpt-4o-mini` with structured JSON output, falling back to deterministic heuristics on timeout/error, and normalizing layouts to standard 24-column rows.
- **Frontend Integration** (`CreateDashboardModal.jsx`, `AISuggestionDrawer.jsx`, `BuilderInspector.jsx`, `dashboardAi.js`): Auto-generating starter dashboards on creation and in-canvas contextual next-widget suggestions.

During real-world usage with multi-form setups, critical defects were identified:

### 1.1 Root Cause of Dashboard Creation Failure with Multiple Monitoring Forms (HTTP 400)
When creating a dashboard with multiple monitoring forms selected in `CreateDashboardModal`:
1. `CreateDashboardModal` calls `suggestDashboard({ root_form, monitoring_forms })`.
2. In `backend/api/v1/v1_visualization/ai/ai_service.py:465-481` (`validate_and_sanitize_widgets`):
   ```python
   if not col_qid or col_qid not in sources_map.get(target_form or form_id or 0, {}):
       # Try other form in sources_map if misplaced
       found_fid = None
       for fid, qmap in sources_map.items():
           if col_qid in qmap:
               found_fid = fid
               break
       if not found_fid:
           continue
       col_qid = int(col_qid)
   ```
   When OpenAI or candidate generation assigns a question from `monitoring_form_2` to a table widget on `monitoring_form_1`, `validate_and_sanitize_widgets` finds `found_fid` in `monitoring_form_2` and **keeps `source: "answer"` with `question: col_qid`**!
3. `CreateDashboardModal` takes `aiRes.data.widgets` and posts to `POST /api/v1/manage/dashboards`.
4. In `backend/api/v1/v1_visualization/dashboard_functions.py:893`, `validate_dashboard_payload` evaluates:
   ```python
   elif source == "answer":
       if form is None or col_q.form_id != form.id:
           return _error("column question must belong to the widget's form", index, "config.columns")
   ```
   Because `col_q.form_id` (`monitoring_form_2`) does NOT match the table's `form.id` (`monitoring_form_1`), **`validate_dashboard_payload` rejects the creation payload with HTTP 400 Bad Request**!
5. In `CreateDashboardModal.jsx`, `doCreate` catches the 400 error, displays `"Something went wrong"`, and aborts dashboard creation!

### 1.2 Root Cause of Raw ID on Chart X-Axis Dropdowns (Chart Options Inspector)
When a user selects a chart in the Dashboard Builder, the right-hand inspector panel displays the chart's configuration options (including "X axis (date question)" for line charts, "X axis (number or autofield)" for scatter plots, and "Question" for bar charts). These dropdowns showed raw integer IDs (e.g. `1749631041155`) instead of question labels due to:
1. **Dropdown Option Desync & Misplaced Questions**: When AI generated a widget referencing a question from another form or a question whose type did not match the dropdown filter (e.g. non-numeric question on scatter X-axis, date question from registration form on a monitoring line chart), Ant Design's `<Select>` could not find a matching `<Select.Option>`. Ant Design falls back to rendering the raw value string (`1749631041155`).
2. **Autofield & Zero-Option Question Ingestion**: In `ai_heuristics.py`, `_find_questions_by_type` bundled `QuestionTypes.autofield` with `QuestionTypes.option`. Because autofield and option questions with no options (`option_count == 0`) have no `QuestionOptions` rows, grouping by them produced either empty chart data ("No data available") or auto-increment integer IDs as category labels.
3. **Inspector Fail-Safe Resolution**: In `BuilderInspector.jsx`, `findQuestionInFamily` was implemented to look up any unlisted question across all forms in the family, injecting a `<Select.Option>` with the question label (and source form badge) for `widget.question`, `date_question_id`, `question_y`, `category_question_id`, and `value_question`, alongside inline form-switch auto-healing.
4. **Missing Axis Labels**: AI generation omitted `config.x_axis_label` and `config.y_axis_label`, now auto-populated from natural language question names.

### 1.3 Root Cause of Multi-Monitoring Form Disregard
In `ai_heuristics.py`, `generate_starter_heuristics` exclusively inspected `monitoring_forms[0]`, entirely ignoring subsequent monitoring forms selected in the modal.

---

## 2. 5W1H Requirements Analysis

| Dimension | Specification |
|---|---|
| **Who** | Dashboard authors creating dashboards across single or multiple monitoring forms. |
| **What** | Fix creation failure by eliminating cross-form column leaks in `ai_service.py`, enforce strict parity with `validate_dashboard_payload`, guard `option_count > 0`, auto-populate axis labels, and iterate across all selected monitoring forms. |
| **Where** | `backend/api/v1/v1_visualization/ai/`, `backend/api/v1/v1_visualization/dashboard_functions.py`, and `frontend/src/pages/dashboards/` |
| **When** | Triggered during dashboard creation with AI starter, in-canvas AI suggestions, and widget inspection. |
| **Why** | Prevents creation HTTP 400 failures, guarantees human-readable question names on chart axes and dropdowns, eliminates empty charts, and isolates each monitoring form cleanly. |
| **How** | Prune cross-form table columns strictly in `validate_and_sanitize_widgets`, validate candidate widgets against `_validate_widget`, loop through all monitoring forms independently, and provide frontend resilience. |

---

## 3. High-Level Architecture & Data Flow

```mermaid
flowchart TD
    Req[POST /manage/dashboards/ai/suggest-dashboard\n{ root_form, monitoring_forms: [Form A, Form B] }] --> Service[AISuggestionService]
    Service --> Meta[extract_family_metadata\nExtract root + monitoring forms A & B with option counts]

    Meta --> Engine{OpenAI Configured?}
    Engine -- Yes --> AI[OpenAI gpt-4o-mini\nPrompt: Multi-monitoring isolation + option_count >= 2]
    Engine -- No --> Heuristics[generate_starter_heuristics\nLoop over root form + Form A + Form B independently]

    AI --> RawWidgets[Raw Widget Candidates]
    Heuristics --> RawWidgets

    RawWidgets --> Sanitizer[validate_and_sanitize_widgets]
    Sanitizer --> Check1{Question belongs to widget.form?}
    Check1 -- No --> Prune1[Prune Widget]
    Check1 -- Yes --> Check2{Table column source vs form valid?}
    Check2 -- No --> CleanCols[Drop invalid cross-form columns]
    Check2 -- Yes --> Check3{group_by == 'option' & option_count > 0?}
    Check3 -- No --> Prune2[Prune empty option widgets]
    Check3 -- Yes --> Gate[_validate_widget Parity Gate\nValidate against exact backend dashboard rules]

    Gate -- Passes --> Label[Populate x_axis_label / y_axis_label]
    Gate -- Fails --> DropInvalid[Drop Widget]

    Label --> Normalized[normalize_grid_layout]
    Normalized --> Res[200 OK Response]
    Res --> UI[CreateDashboardModal: POST /manage/dashboards]
    UI --> ValidatePayload[validate_dashboard_payload: 100% Passes Guaranteed]
    ValidatePayload --> Success[201 Created & Canvas Rendered]
```

---

## 4. BMAD Council Deliberation & Defense-in-Depth Consensus 🎭

The council convened to establish a 4-tier defense-in-depth architecture to ensure cross-form leaks, creation failures, and raw IDs cannot reoccur:

### 4.1 🏗️ Winston (System Architect) — Invariants & Validator Parity
- **Invariant 1: Absolute Single-Form Containment**: Every suggested widget MUST be self-contained within its declared `widget.form`. All referenced question IDs (`question`, `config.date_question_id`, `config.question_y`, `config.stack_question`, `config.value_question`, and table columns) MUST belong strictly to `widget.form` (or `root_form` for `parent_answer`).
- **Invariant 2: Zero Validator Disparity**: `validate_and_sanitize_widgets` must run every candidate widget through the exact same `_validate_widget` logic from `dashboard_functions.py` before returning suggestions. Any widget that would trigger an HTTP 400 during `create` is pruned immediately.
- **Invariant 3: Option Validity Rule**: Categorical charts (`bar`, `pie`) with `group_by: "option"` are ONLY valid if the target question is an option/multiple-option question with `option_count >= 1`.
- **Invariant 4: Zero Cross-Monitoring Interaction**: No chart or table may reference questions across two different monitoring forms.

### 4.2 💻 Amelia (Senior Developer) — Implementation & Self-Healing
- **Backend Table Column Fix**: In `validate_and_sanitize_widgets`, remove the cross-form search loop (`for fid, qmap in sources_map.items()`). If a column with `source == "answer"` does not belong to `widget.form`, drop the column. If a column with `source == "parent_answer"` does not belong to `root_form`, drop the column.
- **Automatic Axis Label Injection**: AI generation must populate `config.x_axis_label` and `config.y_axis_label` from the resolved question label so chart axes always carry human-readable titles.
- **Frontend Inspector Healing**: In `BuilderInspector.jsx`, if `widget.question` is an ID not found in `questionsForForm(widget.form)`:
  - Search all forms in `sources.forms`. If the question belongs to another form, gracefully display the question name along with the form name, and provide a one-click auto-heal button to switch `widget.form` to the owning form. Never display a bare raw integer ID.
- **Frontend Creation Fallback**: In `CreateDashboardModal.jsx`, if `doCreate` with starter widgets receives a 400 error, retry creation without widgets so the user never gets completely blocked from creating a dashboard.

### 4.3 🧪 Murat (Test Architect) — Edge Cases & Regression Strategy
- **Edge Case Matrix**:
  1. *Dashboard creation with multiple monitoring forms (Form A + Form B)*: Assert `POST /manage/dashboards/ai/suggest-dashboard` returns valid widgets for both forms, and assert `POST /manage/dashboards` succeeds with `201 Created`!
  2. *Cross-form column leak regression test*: In `tests_ai_visualization.py`, inject a table on Form A with column question from Form B. Verify `validate_and_sanitize_widgets` removes the invalid column and produces a payload that passes `validate_dashboard_payload`.
  3. *Monitoring form with 0 date questions*: Heuristics must skip line trend, avoid crashing, and generate categorical/table widgets instead.
  4. *Form with 0 option questions or where all options have `option_count == 0`*: Heuristics must not generate empty Bar/Pie charts.
  5. *Axis label assertions*: Verify `x_axis_label` is always populated and matches the natural language question name.

### 4.4 🛡️ Rachel (Security Red Team) — Scope Boundaries & Threat Prevention
- **Tenant Isolation**: `extract_family_metadata` and `sources` strictly enforce `Forms.objects.for_user(request.user)`.
- **Payload Integrity**: Pruning cross-form questions prevents cross-form data probing through crafted suggestion payloads.
- **XSS Prevention**: Question labels injected into `x_axis_label` and `y_axis_label` are sanitized strings to prevent script injection in chart tooltips or axis containers.

---

## 5. Detailed Technical Specifications

### 5.1 Backend Hardening (`backend/api/v1/v1_visualization/ai/`)

#### 5.1.1 Schema Extraction (`ai_service.py`)
- In `extract_family_metadata`:
  - `option` and `multiple_option`: `opt_count = len(all_opts)`.
  - `autofield`, `number`, `date`, `geo`: `opt_count = 0`.
  - Ensure `q_info["option_count"] = opt_count`.

#### 5.1.2 Validator & Sanitizer (`ai_service.py: validate_and_sanitize_widgets`)
- **Fix Table Column Cross-Form Leaks**:
  ```python
  if w_type == "table":
      cols = config.get("columns")
      valid_cols = []
      if isinstance(cols, list):
          for col in cols:
              if not isinstance(col, dict):
                  continue
              src = col.get("source")
              if src not in (
                  "parent_name",
                  "administration",
                  "answer",
                  "parent_answer",
                  "latest_date",
              ):
                  continue
              col_qid = col.get("question") or col.get("question_id")
              if src == "answer":
                  # Must belong to widget.form
                  if not col_qid or col_qid not in sources_map.get(form_id or 0, {}):
                      continue
              elif src == "parent_answer":
                  # Must belong to root_form
                  if not col_qid or col_qid not in sources_map.get(root_form_id or 0, {}):
                      continue
              elif src == "latest_date":
                  if col_qid and col_qid not in sources_map.get(form_id or 0, {}):
                      continue
              valid_cols.append({
                  "key": col.get("key") or f"col_{len(valid_cols)}",
                  "source": src,
                  "question": int(col_qid) if col_qid else None,
                  "label": col.get("label") or col.get("key") or "Column",
              })
      if not valid_cols:
          valid_cols = _build_default_table_columns(
              form_id=form_id,
              root_form_id=root_form_id,
              sources_map=sources_map,
          )
      config["columns"] = valid_cols
      # Table widgets do not have a measure
      config.pop("measure", None)
  ```
- **Categorical Option Guard**:
  ```python
  if w_type in ("bar", "pie") and config.get("group_by") == "option":
      q_info = sources_map.get(form_id, {}).get(q_id, {})
      if q_info.get("type") not in (QuestionTypes.option, QuestionTypes.multiple_option):
          continue
      if q_info.get("option_count", 0) <= 0:
          continue
  ```
- **Secondary Question Validation**:
  ```python
  # Validate date_question_id
  date_qid = config.get("date_question_id")
  if date_qid:
      target_qs = sources_map.get(form_id, {})
      if date_qid not in target_qs or target_qs[date_qid].get("type") != QuestionTypes.date:
          config["date_question_id"] = None

  # Validate question_y
  qy = config.get("question_y")
  if qy:
      target_qs = sources_map.get(form_id, {})
      if qy not in target_qs or target_qs[qy].get("type") not in NUMERIC_QUESTION_TYPES:
          config["question_y"] = None

  # Disallow cross-monitoring stack_form
  if config.get("stack_form") and config.get("stack_form") != form_id:
      config["stack_form"] = None
      config["stack_question"] = None
  ```
- **Axis Label Auto-Population**:
  ```python
  q_info = sources_map.get(form_id, {}).get(q_id, {})
  q_label = q_info.get("label") or q_info.get("name")
  if w_type == "bar":
      if config.get("orientation") == "horizontal":
          config.setdefault("y_axis_label", q_label)
      else:
          config.setdefault("x_axis_label", q_label)
  elif w_type == "line":
      date_qid = config.get("date_question_id")
      date_label = sources_map.get(form_id, {}).get(date_qid, {}).get("label") if date_qid else None
      if date_label:
          config.setdefault("x_axis_label", date_label)
      if q_label:
          config.setdefault("y_axis_label", q_label)
  elif w_type == "scatter":
      if q_label:
          config.setdefault("x_axis_label", q_label)
      qy = config.get("question_y")
      qy_label = sources_map.get(form_id, {}).get(qy, {}).get("label") if qy else None
      if qy_label:
          config.setdefault("y_axis_label", qy_label)
  ```

#### 5.1.3 Heuristics Multi-Monitoring Loop (`ai_heuristics.py: generate_starter_heuristics`)
- Enforce `option_count > 0` before selecting any question for `_create_pie_widget` or `_create_bar_widget`.
- Iterate through **all** forms in `monitoring_forms`:
  ```python
  for m_form in monitoring_forms:
      m_id = m_form.get("id")
      m_name = m_form.get("name", "Monitoring")
      m_questions = m_form.get("questions", [])

      # 1. Line widget for date question (if present)
      date_qs = _find_questions_by_type(m_questions, [QuestionTypes.date])
      if date_qs:
          widgets.append(_create_line_widget(
              form_id=m_id,
              date_q_id=date_qs[0]["id"],
              title=f"{m_name} Activity Over Time",
              rationale=f"Trend tracking by {date_qs[0]['label']}.",
              col_span=12,
              measure="all_submissions",
              x_axis_label=date_qs[0]["label"],
          ))

      # 2. Categorical widget for option question (if option_count > 0)
      opt_qs = [
          q for q in _find_questions_by_type(m_questions, [QuestionTypes.option, QuestionTypes.multiple_option])
          if q.get("option_count", 0) > 0
      ]
      if opt_qs:
          widgets.append(_create_bar_widget(
              form_id=m_id,
              question_id=opt_qs[0]["id"],
              title=f"{m_name} {opt_qs[0]['label']} Breakdown",
              rationale=f"Distribution of {opt_qs[0]['label']}.",
              col_span=12,
              measure="current_state",
              x_axis_label=opt_qs[0]["label"],
          ))

      # 3. Table widget for monitoring form
      widgets.append(_create_table_widget(
          form_id=m_id,
          title=f"Recent {m_name} Log",
          rationale=f"Detailed log of submissions for {m_name}.",
          col_span=24,
          questions=m_questions,
          root_questions=root_questions,
      ))
  ```

#### 5.1.4 Prompt Isolation Directives (`ai_prompts.py`)
- Add mandatory system rules:
  1. `"MULTI-MONITORING FORM ISOLATION: When multiple monitoring forms are present, generate independent widgets for EACH monitoring form. NEVER mix questions or IDs from different forms within the same widget. Zero cross-form charts or tables are permitted."`
  2. `"NON-EMPTY OPTION CONSTRAINT: Bar and pie charts with group_by: 'option' MUST ONLY be assigned to questions where option_count >= 2. NEVER assign categorical charts to questions with option_count == 0, autofield, or text questions."`
  3. `"AXIS LABELS: Always set config.x_axis_label and config.y_axis_label matching the question labels."`

---

### 5.2 Frontend Hardening (`frontend/src/pages/dashboards/`)

#### 5.2.1 Question Dropdown Display & Auto-Healing (`BuilderInspector.jsx`)
- When rendering `<Select value={widget.question || null}>`:
  - If `widget.question` is an ID not found in `questionsForForm(widget.form)`:
    - Search across all forms in `sources.forms`.
    - If found in form $F_{found}$:
      - Render `<Select.Option value={widget.question} label={foundQ.label}>` with an indicator tag `[Belongs to ${F_{found}.name}]`.
      - Show an inline alert: *"This question belongs to ${F_{found}.name}. Switch widget data source?"* with an auto-heal button that sets `widget.form = F_{found}.id`.
  - Ensure the `X axis label` input field in `SUPPORTS_AXIS_LABELS` initializes with `wConfig.x_axis_label || selectedQuestion?.label || ""`.

#### 5.2.2 Modal Creation Resilience (`CreateDashboardModal.jsx`)
- If `doCreate(createPayload)` fails with status 400 and `starterWidgets` was included:
  - Gracefully retry creation without widgets (`doCreate({ ...createPayload, widgets: undefined })`), display a warning: `"Dashboard created, but some AI widgets could not be applied."`, and open the builder cleanly.

---

## 6. Verification & Automated Testing Plan

### 6.1 Backend Automated Tests (`tests_ai_visualization.py`)
- `test_starter_heuristics_multiple_monitoring_forms`: Verify that passing 2+ monitoring forms generates distinct widgets for each monitoring form without cross-form references.
- `test_multi_monitoring_starter_widgets_pass_validate_dashboard_payload`: Verify that the entire `widgets` array returned by `suggest_dashboard` with multiple monitoring forms passes `validate_dashboard_payload` with zero validation errors!
- `test_cross_monitoring_table_columns_strictly_pruned`: Verify that a table widget on Form A referencing columns from Form B has those columns pruned.
- `test_zero_option_question_not_selected_for_categorical_chart`: Verify that an option question with 0 options is not selected for bar/pie charts.
- `test_autofield_question_not_selected_for_option_grouping`: Verify that autofield questions are not assigned `group_by: "option"`.
- `test_x_axis_label_populated_on_ai_widgets`: Verify that `x_axis_label` is automatically populated with the question label for bar, line, and scatter widgets.

### 6.2 Frontend Automated Tests
- `CreateDashboardModalAI.test.js`: Verify modal creates dashboard successfully when multiple monitoring forms are selected with AI enabled.
- `BuilderInspector.test.js`: Verify question dropdown displays question label and never raw ID when inspecting AI-generated widgets, and handles cross-form healing.

---

## 7. Epic & Vibe Coding Estimation ⏱️

- **Confidence Level**: High
- **Dependencies**: None (builds directly on `VIZ-AI-002` and `VIZ-AI-003`)

| Task ID | Component & Description | Vibe Coding (Dev) | Automated Testing | QA & Review | Total Est. Time | Priority |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TASK-01** | **Backend Table Column & Validator Disparity Fix**: Eliminate cross-form column leaks in `ai_service.py`, enforce strict parity with `validate_dashboard_payload`, guard `option_count > 0`, auto-populate `x_axis_label`. | 50m | 35m | 20m | **105m (1.75h)** | P0 |
| **TASK-02** | **Multi-Monitoring Form Isolation Engine**: Loop over all selected monitoring forms in `ai_heuristics.py`, add prompt isolation rules in `ai_prompts.py`, and prune cross-monitoring references in `validate_and_sanitize_widgets`. | 45m | 35m | 25m | **105m (1.75h)** | P0 |
| **TASK-03** | **Frontend Creation Resilience & Inspector Healing**: Add creation retry fallback in `CreateDashboardModal.jsx`, heal question labels and avoid raw IDs in `BuilderInspector.jsx`. | 35m | 25m | 20m | **80m (1.3h)** | P1 |
| **TASK-04** | **End-to-End Regression & Verification**: Run backend test suite (`tests_ai_visualization.py`) and frontend tests (`npm test`), verify with multi-form fixtures. | 20m | 15m | 10m | **45m (0.8h)** | P1 |
| **TOTAL** | **Full Feature Delivery** | **2.5h (150m)** | **1.85h (110m)** | **1.25h (75m)** | **5.6h (335m)** | - |

---

## 8. Data Availability Guard & Empty Chart Prevention 🛡️

To prevent the AI from creating charts or tables that display "No data available" when users select newly added monitoring forms that have no submission data:
1. **Indexed Aggregation in `extract_family_metadata`**:
   - Computes `submission_count` per form via `FormData.objects.filter(...)`.
   - Computes `answer_count` per question via `Answers.objects.filter(...)`.
   - Evaluates `total_submissions` across the active form family.
2. **Heuristic & Prompt Guard**:
   - When active submissions exist in the family (`total_submissions > 0`), skips generating line, bar, pie, and table widgets for any monitoring form with `submission_count == 0`.
   - Only selects questions with `answer_count > 0` for primary chart visualizations.
   - Prompt instructs OpenAI to never generate chart widgets for forms or questions with 0 data points.
3. **Sanitization Gate**:
   - `validate_and_sanitize_widgets` prunes any candidate chart targeting a form with 0 submissions or a question with 0 answers when active submissions exist in the family.
