# Design Spec: VIZ-AI-005 Multi-Monitoring Form Section Titles & Visual Grouping 📑

## 1. Context & Problem Statement
When generating dashboards across form families that include multiple monitoring forms (e.g. *Registration*, *Water Quality Monitoring*, *Maintenance & Repairs Monitoring*), AI layout generation creates 10–15 widgets sequentially on the canvas.

Currently, there are **no visual dividing lines or section headers** between data sources. Users cannot immediately determine which monitoring form a specific line chart, bar chart, or data table originates from without reading fine-print widget titles.

By grouping widgets under distinct **`section_title` (type `7`)** headers:
1. **Source Transparency**: Each monitoring form is clearly introduced with a full-width header (`w: 24`).
2. **Cognitive Clarity**: Users instantly understand the reporting domain (Overview vs. Water Quality vs. Maintenance).
3. **Native Alignment**: Leverages the existing `VizSectionTitle` React component and `WidgetTypes.section_title = 7` backend definition.

---

## 2. Architecture & Data Contracts

### 2.1 The `section_title` Contract
`WidgetTypes.section_title` (ID `7`) in `backend/api/v1/v1_visualization/constants.py`:
- **`type`**: `"section_title"`
- **`title`**: String (max 255 chars), e.g. `"Water Quality Monitoring"` or `"Facility Overview"`
- **`col_span`**: `24` (strictly full row in the 24-column grid)
- **`form`**: `m_id` or `root_id` (indicates which source form this section represents)
- **`question`**: `None` (does not bind to questions)
- **`config`**: `{"text": "<Title>"}`
- **`data fetching`**: Pure UI component — network fetching is bypassed in `useWidgetData.js`.

### 2.2 Layout & Grid Row Balancing
In `normalize_grid_layout` (`ai_service.py`):
```python
if w.get("type") in ("table", "map", "section_title"):
    w["col_span"] = 24
```
Because `col_span == 24`, a section title always begins on a fresh row and takes up the entire width of the dashboard.

---

## 3. Heuristic Generator Rules (`ai_heuristics.py`)

### Scenario A: Registration + Monitoring Forms (`has_monitoring == True`)
1. **Section 1 (Root Overview)**:
   - Insert `section_title`: `title = f"{root_name} Overview"`
   - Followed by: Root KPI(s), Pie/Bar categorical breakdown, Geographic Map.
2. **Section 2..N (Each Active Monitoring Form)**:
   - For each active monitoring form in `monitoring_forms`:
     - Skip if form has 0 submissions (`submission_count == 0` when `total_submissions > 0`).
     - Insert `section_title`: `title = m_name`
     - Followed by: Line activity chart, Bar distribution chart, Recent submissions table.

### Scenario B: Registration Only (`has_monitoring == False`)
- If only a registration form exists with 3–4 widgets, section titles are omitted to avoid unnecessary visual clutter.

---

## 4. AI Sanitizer & Defense Gates (`ai_service.py`)

1. **`type_map` Addition**:
   Register `WidgetTypes.section_title: "section_title"`, `"section_title": "section_title"`.
2. **Question Exemption**:
   Bypass question checks when `w_type == "section_title"`.
3. **Data Availability Guard & Orphan Header Pruning**:
   - If a candidate `section_title` has a `form` assigned and that monitoring form has 0 submissions (`form_subs[w_form] == 0` when `total_subs > 0`), **drop the section title**.
   - No orphan section titles without content will ever appear on the canvas.

---

## 5. OpenAI Prompt Directive (`ai_prompts.py`)
Add instructions in Section 6 (`MULTI-MONITORING FORM ISOLATION & SECTION GROUPING`):
> When multiple forms are present in the family, prefix each form's group of widgets with a `section_title` widget (`col_span: 24`, `question: null`, `config: {"text": "<Form Name>"}`).

---

## 6. Implementation Task Breakdown

| Task ID | Description | Vibe Coding (Dev) | Automated Testing | QA & Review | Total Est. | Priority |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TASK-01** | **Backend AI Sanitizer & Grid Layout**: Add `section_title` to `type_map`, enforce `col_span: 24`, and apply orphan header pruning. | 15m | 15m | 10m | **40m (0.7h)** | P1 |
| **TASK-02** | **Heuristics & Prompt Generator**: Insert section titles before root and each active monitoring form in `ai_heuristics.py` and `ai_prompts.py`. | 20m | 15m | 10m | **45m (0.8h)** | P1 |
| **TASK-03** | **Automated Test Coverage**: Write tests for section title generation, grid balance, and orphan pruning in `tests_ai_visualization.py`. | 15m | 20m | 10m | **45m (0.8h)** | P1 |
| **TOTAL** | **Full Feature Delivery** | **50m** | **50m** | **30m** | **130m (2.2h)** | - |

