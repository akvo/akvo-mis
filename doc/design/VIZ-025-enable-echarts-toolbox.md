# Feature Design Document: [VIZ-025] Enable ECharts Toolbox for Each Chart

> **Purpose**: Standard Akvo MIS feature planning document aligned with `doc/templates/FEATURE_DESIGN_TEMPLATE.md`. Complete this document BEFORE implementation begins.
>
> - **Location**: `doc/design/VIZ-025-enable-echarts-toolbox.md`
> - **Path Standard**: Strictly use **project-root-relative paths** (e.g., `/frontend/src/components/dashboard/...`, `/frontend/src/pages/dashboards/...`). NEVER include machine-specific absolute paths or usernames.

---

## Feature: [VIZ-025] Enable ECharts Toolbox for Each Chart

**Task ID**: VIZ-025
**Author**: Galih Pratama / Antigravity Agent
**Date**: 2026-09-10
**Status**: Draft

---

## 1. Context & Problem Statement

Currently:
- Dashboard charts (Bar, StackBar, Line, StackLine, Pie, Doughnut, Scatter) render static ECharts views without built-in interaction tools.
- Users viewing dashboards cannot easily download high-res chart images (`saveAsImage`), inspect underlying data tables (`dataView`), zoom into dense time series or scatter points (`dataZoom`), or reset chart states (`restore`).
- `akvo-charts` (upgraded to `^1.3.9`) and underlying ECharts support the `toolbox` configuration natively.

Goal:
- Provide a configurable option in the Dashboard Builder Inspector to enable/customize ECharts Toolbox for chart widgets (`bar`, `line`, `pie`, `scatter`).
- Render toolbox actions cleanly in both the Dashboard Builder preview and the published Dashboard Viewer.

---

## 2. Requirements

### User Acceptance Criteria (UAC)

- [ ] In Dashboard Builder, selecting a chart widget (Bar, Line, Pie, Scatter) displays a "Toolbox Options" setting in the Inspector panel.
- [ ] Users can toggle the Toolbox ON/OFF for each chart widget independently (defaults to OFF).
- [ ] Users can adjust the toolbox position (`top-right`, `top-left`, `bottom-right`, `bottom-left`).
- [ ] Users can select which toolbox features to enable:
  - **Save as Image** (`saveAsImage`) - Downloads current chart as PNG.
  - **Data View** (`dataView`) - Opens modal table showing raw category/value data.
  - **Restore** (`restore`) - Resets filters/zoom on the chart.
  - **Data Zoom** (`dataZoom`) - Allows box and wheel zoom (for Bar, Line, Scatter).
- [ ] In Dashboard Viewer (and builder canvas), charts with toolbox enabled display the toolbox icons in the designated position.
- [ ] Non-chart widgets (KPI, Table, Map, Section Title) do not show toolbox options.

### Technical Acceptance Criteria (TAC)

- [ ] Stored in widget JSON configuration (`widget.config.show_toolbox`, `widget.config.toolbox_position`, `widget.config.toolbox_features`).
- [ ] Works seamlessly with both `akvo-charts` components (`Bar`, `StackBar`, `Line`, `StackLine`, `Pie`, `Doughnut`) and custom ECharts options (`useEChartsOption`, `rawConfig`).
- [ ] No database schema migrations required (uses existing `JSONField` `config` on `DashboardWidget`).
- [ ] Backward compatibility: existing dashboards without toolbox config render with toolbox disabled by default.

---

## 3. Data Model Changes

### New Models

*None required.*

### Modified Models

*None required.* `DashboardWidget.config` is a `JSONField` that stores widget-specific presentation settings:

```json
// Example widget.config
{
  "group_by": "option",
  "chart_colors": ["#1890ff", "#64A73B"],
  "show_toolbox": false,
  "toolbox_position": "top-right",
  "toolbox_orient": "horizontal",
  "toolbox_features": {
    "saveAsImage": true,
    "dataView": true,
    "restore": true,
    "dataZoom": true
  }
}
```

### Migration Strategy

*No database migrations needed.* Existing dashboard widgets will have `show_toolbox: false` (or `undefined`), preserving current behavior.

---

## 4. API Contract

### Endpoints

*Existing dashboard CRUD and publish endpoints handle widget `config` transparently:*

- `GET /api/v1/dashboards/:id`
- `PUT /api/v1/dashboards/:id`
- `POST /api/v1/dashboards/:id/publish`
- `GET /api/v1/dashboards/read/:id`

---

## 5. Decision Log

### D-1: Granular Features vs Simple Toggle

**Options Considered**:

1. Single boolean toggle (`show_toolbox: true/false`) with fixed default features (`saveAsImage`, `dataView`, `restore`, `dataZoom`).
2. Granular feature checkboxes (`saveAsImage`, `dataView`, `restore`, `dataZoom`) with a master toggle and adjustable position (`top-right`, `top-left`, `bottom-right`, `bottom-left`).

**Decision**: Option 2 (Master toggle + feature checklist + position selector, defaulting to `show_toolbox: false`).

**Rationale**:
- `show_toolbox: false` by default keeps charts clean unless authors explicitly enable it.
- Omitting `magicType` prevents chart type mismatch with dashboard widget configurations (e.g. converting a customized stacked bar into a line chart breaks visual intent and legends).
- Position selector prevents toolbox icons from overlapping chart titles, legends, or data labels.

**Impact**: Flexible UI in `BuilderInspector.jsx` and standardized helper to build ECharts `toolbox` config.

---

## 6. Type/Constant Mappings

| Feature Key | ECharts Feature | Description | Supported Chart Types |
| :--- | :--- | :--- | :--- |
| `saveAsImage` | `feature.saveAsImage` | Download chart image (PNG/JPG) | Bar, Line, Pie, Scatter |
| `dataView` | `feature.dataView` | View raw data table modal | Bar, Line, Pie, Scatter |
| `restore` | `feature.restore` | Reset chart zoom/filters to initial state | Bar, Line, Pie, Scatter |
| `dataZoom` | `feature.dataZoom` | Interactive selection zoom & reset | Bar, Line, Scatter |

### Toolbox Position Presets

| Position Preset | ECharts Coordinates | Orient |
| :--- | :--- | :--- |
| `top-right` (Default) | `{ top: 0, right: 10 }` | `horizontal` |
| `top-left` | `{ top: 0, left: 10 }` | `horizontal` |
| `bottom-right` | `{ bottom: 0, right: 10 }` | `horizontal` |
| `bottom-left` | `{ bottom: 0, left: 10 }` | `horizontal` |

---

## 7. Compatibility & Migration

### Backward Compatibility

- [x] Existing dashboards without toolbox settings continue to render cleanly with toolbox hidden (`show_toolbox: false`).
- [x] Embedded dashboards and public dashboards render toolbox if enabled in config.

### Mobile App Impact

- [x] No mobile app impact (dashboards are web-only).

---

## 8. Security & Multi-Tenancy Considerations

- [x] All widget configs remain scoped within the tenant dashboard boundary.
- [x] DataView feature only displays data already fetched and authorized by `/api/v1/visualization/values`.

---

## 9. Testing Strategy

| Test Type | Scope / Target | Command |
| :--- | :--- | :--- |
| Frontend Component Test | `/frontend/src/pages/dashboards/__test__/BuilderInspector.test.js` | `./dc.sh exec frontend npm test BuilderInspector` |
| Frontend Widget Test | `/frontend/src/components/dashboard/__test__/VizBar.test.js` | `./dc.sh exec frontend npm test VizBar` |
| Frontend Parity Test | `/frontend/src/pages/dashboards/__test__/viewerPreviewParity.test.js` | `./dc.sh exec frontend npm test viewerPreviewParity` |

---

## 10. Open Questions

- [x] **Resolved**: `show_toolbox` defaults to `false`.
- [x] **Resolved**: `magicType` excluded to preserve chart type integrity.
- [x] **Resolved**: Position is configurable (`top-right`, `top-left`, `bottom-right`, `bottom-left`).

---

## 11. Epic & Vibe Coding Estimation ⏱️

- Confidence Level: High
- Dependencies: `akvo-charts: ^1.3.9`

| Task ID | Story / Task Description | Vibe Coding (Dev) | Automated Testing | QA & Review | Total Est. Time | Priority |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TASK-01** | Create `buildToolboxConfig` helper in `/frontend/src/components/dashboard/widgets/` | 15m | 10m | 10m | **35m (0.6h)** | Must Have |
| **TASK-02** | Update `VizBar`, `VizLine`, `VizPie`, `VizScatter` to apply `toolbox` config | 25m | 20m | 15m | **60m (1.0h)** | Must Have |
| **TASK-03** | Add Toolbox Controls (Switch, Position Selector & Feature Checklist) in `BuilderInspector.jsx` | 30m | 20m | 15m | **65m (1.1h)** | Must Have |
| **TASK-04** | Update default widget constants in `builderConstants.js` and add unit tests | 20m | 20m | 10m | **50m (0.8h)** | Must Have |

---

## 12. References & Approvals

- [Akvo Charts Toolbox Documentation](https://github.com/akvo/akvo-charts/#toolbox)

| Role | Name | Date | Status |
| :--- | :--- | :--- | :--- |
| Developer | Galih Pratama | 2026-09-10 | Approved |
| Tech Lead | | | |
| Product | | | |

