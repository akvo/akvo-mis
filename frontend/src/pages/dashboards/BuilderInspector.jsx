import React, { useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import { Input, InputNumber, Select, Switch, Checkbox } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import {
  NEEDS_FORM,
  NEEDS_QUESTION,
  NEEDS_GROUP_BY,
  NEEDS_STACK_BY,
  NEEDS_VALUE_TYPE,
  NEEDS_REPEAT_AGG,
  NEEDS_COLOR,
  VALID_GROUP_BY,
  VALID_VALUE_TYPE,
  VALID_REPEAT_AGG,
  VALID_STACK_BY,
  VALID_ORIENTATION,
  VALID_PIE_VARIANT,
  VALID_MEASURE,
  VALID_CRITERIA_TYPES,
  WIDTH_PRESETS,
  COLOR_SWATCHES,
  TYPE_LABELS,
  defaultMeasure,
  pruneConfigForForm,
} from "./builderConstants";

const { TextArea } = Input;

const BuilderInspector = ({
  widget,
  sources,
  dashboardName,
  dashboardDesc,
  defaultFilters,
  onWidgetChange,
  onDashboardChange,
  errorMessage,
}) => {
  const forms = useMemo(() => sources?.forms || [], [sources]);

  const isMonitoringForm = useCallback(
    (formId) => {
      const form = forms.find((f) => f.id === formId);
      return form?.type === "monitoring";
    },
    [forms]
  );

  const questionsForForm = useCallback(
    (formId) => {
      const form = forms.find((f) => f.id === formId);
      return form?.questions || [];
    },
    [forms]
  );

  const updateWidget = useCallback(
    (field, value) => {
      onWidgetChange({ ...widget, [field]: value });
    },
    [widget, onWidgetChange]
  );

  const updateConfig = useCallback(
    (field, value) => {
      onWidgetChange({
        ...widget,
        config: { ...widget.config, [field]: value },
      });
    },
    [widget, onWidgetChange]
  );

  if (!widget) {
    return (
      <div className="builder-inspector">
        <div className="builder-inspector-inner">
          <div className="builder-inspector-heading">Dashboard settings</div>

          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Name</label>
            <Input
              value={dashboardName}
              onChange={(e) => {
                onDashboardChange("name", e.target.value);
              }}
              placeholder="Untitled dashboard"
            />
          </div>

          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Description</label>
            <TextArea
              value={dashboardDesc}
              onChange={(e) => {
                onDashboardChange("description", e.target.value);
              }}
              placeholder="What does this dashboard show?"
              autoSize={{ minRows: 3 }}
            />
          </div>

          <div className="builder-inspector-field">
            <div
              className="builder-inspector-label"
              style={{ marginBottom: 8 }}
            >
              Default filters
            </div>
            <label className="builder-inspector-filter-row">
              Monitoring period
              <Switch
                size="small"
                checked={defaultFilters?.date?.enabled !== false}
                onChange={(checked) => {
                  onDashboardChange("default_filters", {
                    ...defaultFilters,
                    date: { ...defaultFilters?.date, enabled: checked },
                  });
                }}
              />
            </label>
            <label className="builder-inspector-filter-row">
              Location (administration)
              <Switch
                size="small"
                checked={defaultFilters?.administration?.enabled !== false}
                onChange={(checked) => {
                  onDashboardChange("default_filters", {
                    ...defaultFilters,
                    administration: {
                      ...defaultFilters?.administration,
                      enabled: checked,
                    },
                  });
                }}
              />
            </label>
          </div>

          <div className="builder-inspector-info">
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              style={{ flex: "none", marginTop: 1 }}
            >
              <circle
                cx="12"
                cy="12"
                r="9"
                stroke="#1651b6"
                strokeWidth="1.6"
              />
              <path
                d="M12 11v5M12 8h.01"
                stroke="#1651b6"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
            <div>
              Select any widget on the canvas to configure its data source and
              appearance here.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const wType = widget.type;
  const wConfig = widget.config || {};
  const showForm = NEEDS_FORM.has(wType);
  const showQuestion = NEEDS_QUESTION.has(wType);
  const isMonitoring = showForm && isMonitoringForm(widget.form);
  const questions = showQuestion ? questionsForForm(widget.form) : [];
  const selectedQuestion = questions.find((q) => q.id === widget.question);
  const hasOptionQuestion =
    selectedQuestion?.type === "option" ||
    selectedQuestion?.type === "multiple_option";

  return (
    <div className="builder-inspector">
      <div className="builder-inspector-inner">
        <div className="builder-inspector-type-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 15a3 3 0 100-6 3 3 0 000 6z"
              stroke="#1651b6"
              strokeWidth="1.7"
            />
            <path
              d="M19 12a7 7 0 00-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 00-1.7-1l-.4-2.5H10.6l-.4 2.5a7 7 0 00-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 000 2l-2 1.6 2 3.4 2.4-1a7 7 0 001.7 1l.4 2.5h3.8l.4-2.5a7 7 0 001.7-1l2.4 1 2-3.4-2-1.6a7 7 0 00.1-1z"
              stroke="#1651b6"
              strokeWidth="1.4"
            />
          </svg>
          <span>{TYPE_LABELS[wType] || wType} settings</span>
        </div>

        {errorMessage && (
          <div className="builder-inspector-error">{errorMessage}</div>
        )}

        {/* Title */}
        <div className="builder-inspector-field">
          <label className="builder-inspector-label">Widget title</label>
          <Input
            value={widget.title || ""}
            onChange={(e) => updateWidget("title", e.target.value)}
            placeholder={
              wType === "section_title" ? "Section title" : "Untitled widget"
            }
          />
        </div>

        {/* Heading text (section_title only) */}
        {wType === "section_title" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Heading text</label>
            <Input
              value={wConfig.text || ""}
              onChange={(e) => updateConfig("text", e.target.value)}
              placeholder="Section heading"
            />
          </div>
        )}

        {/* Data source (form) */}
        {showForm && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Data source (form)
            </label>
            <Select
              value={widget.form || null}
              onChange={(val) => {
                // Same rule as the palette's new-widget default, from the
                // same function: a measure the widget's form cannot carry
                // is a 400 at save time, not a UI detail. An existing
                // choice survives a move between two monitoring forms.
                const supported = defaultMeasure(
                  wType,
                  forms.find((f) => f.id === val)
                );
                // Table columns and criteria carry question ids of their
                // own; left behind they point at the previous form and the
                // backend refuses the request.
                const pruned = pruneConfigForForm(
                  widget.config,
                  questionsForForm(val)
                );
                onWidgetChange({
                  ...widget,
                  form: val,
                  question: null,
                  config: {
                    ...pruned,
                    measure: supported
                      ? widget.config?.measure || supported
                      : null,
                  },
                });
              }}
              placeholder="Select a form"
              style={{ width: "100%" }}
              allowClear
            >
              {forms.map((f) => (
                <Select.Option key={f.id} value={f.id}>
                  {f.name}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Measure (monitoring form only, not table) */}
        {showForm && isMonitoring && wType !== "table" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Measure</label>
            <Select
              value={wConfig.measure || "current_state"}
              onChange={(val) => updateConfig("measure", val)}
              style={{ width: "100%" }}
            >
              {VALID_MEASURE.map((m) => (
                <Select.Option key={m.value} value={m.value}>
                  {m.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Include unmonitored sites (monitoring form only, not table) */}
        {showForm && isMonitoring && wType !== "table" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-switch-row">
              <span>Include sites with no data yet</span>
              <Switch
                size="small"
                checked={wConfig.include_unmonitored === true}
                onChange={(checked) => {
                  updateConfig("include_unmonitored", checked);
                }}
              />
            </label>
          </div>
        )}

        {/* Question */}
        {showQuestion && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              {wType === "map" ? "Status question" : "Question"}
            </label>
            <Select
              value={widget.question || null}
              onChange={(val) => updateWidget("question", val)}
              placeholder="Select a question"
              style={{ width: "100%" }}
              allowClear
            >
              {questions.map((q) => (
                <Select.Option key={q.id} value={q.id}>
                  {q.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Group by */}
        {NEEDS_GROUP_BY.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Group by</label>
            <Select
              value={wConfig.group_by || "option"}
              onChange={(val) => updateConfig("group_by", val)}
              style={{ width: "100%" }}
            >
              {VALID_GROUP_BY.map((g) => (
                <Select.Option key={g.value} value={g.value}>
                  {g.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Stack by */}
        {NEEDS_STACK_BY.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Stack by</label>
            <Select
              value={wConfig.stack_by || ""}
              onChange={(val) => updateConfig("stack_by", val || null)}
              style={{ width: "100%" }}
            >
              {VALID_STACK_BY.map((s) => (
                <Select.Option key={s.value} value={s.value}>
                  {s.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Value type */}
        {NEEDS_VALUE_TYPE.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Value type</label>
            <Select
              value={wConfig.value_type || "number"}
              onChange={(val) => updateConfig("value_type", val)}
              style={{ width: "100%" }}
            >
              {VALID_VALUE_TYPE.map((v) => (
                <Select.Option key={v.value} value={v.value}>
                  {v.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Repeat aggregation */}
        {NEEDS_REPEAT_AGG.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Repeat aggregation
            </label>
            <Select
              value={wConfig.repeat_agg || "average"}
              onChange={(val) => updateConfig("repeat_agg", val)}
              style={{ width: "100%" }}
            >
              {VALID_REPEAT_AGG.map((r) => (
                <Select.Option key={r.value} value={r.value}>
                  {r.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Count records where (KPI only, option question) */}
        {wType === "kpi" && hasOptionQuestion && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Count records where
            </label>
            <Select
              value={wConfig.option_value || null}
              onChange={(val) => updateConfig("option_value", val)}
              placeholder="All values"
              style={{ width: "100%" }}
              allowClear
            >
              {(selectedQuestion?.options || []).map((o) => (
                <Select.Option key={o.value} value={o.value}>
                  {o.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Orientation (bar only) */}
        {wType === "bar" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Orientation</label>
            <Select
              value={wConfig.orientation || "vertical"}
              onChange={(val) => updateConfig("orientation", val)}
              style={{ width: "100%" }}
            >
              {VALID_ORIENTATION.map((o) => (
                <Select.Option key={o.value} value={o.value}>
                  {o.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Variant (pie only) */}
        {wType === "pie" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Variant</label>
            <Select
              value={wConfig.variant || "pie"}
              onChange={(val) => updateConfig("variant", val)}
              style={{ width: "100%" }}
            >
              {VALID_PIE_VARIANT.map((v) => (
                <Select.Option key={v.value} value={v.value}>
                  {v.label}
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Table columns */}
        {wType === "table" && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Columns</label>
            <div className="builder-inspector-columns">
              {/* Built-in columns */}
              {[
                { key: "parent_name", label: "Datapoint name" },
                { key: "administration", label: "Administration" },
                { key: "latest_date", label: "Last submission" },
              ].map((col) => {
                const checked = (wConfig.columns || []).some(
                  (c) => c.key === col.key
                );
                return (
                  <label key={col.key} className="builder-inspector-col-row">
                    <Checkbox
                      checked={checked}
                      onChange={(e) => {
                        const cols = wConfig.columns || [];
                        if (e.target.checked) {
                          updateConfig("columns", [
                            ...cols,
                            // The label travels with the column: VizTable
                            // renders `label || key`, so without it the
                            // header read `parent_name` rather than
                            // "Datapoint name".
                            {
                              key: col.key,
                              source: col.key,
                              label: col.label,
                            },
                          ]);
                        } else {
                          updateConfig(
                            "columns",
                            cols.filter((c) => c.key !== col.key)
                          );
                        }
                      }}
                    />
                    {col.label}
                  </label>
                );
              })}
              {/* Question columns */}
              {questionsForForm(widget.form).map((q) => {
                const colKey = `answer_${q.id}`;
                const checked = (wConfig.columns || []).some(
                  (c) => c.key === colKey
                );
                return (
                  <label key={colKey} className="builder-inspector-col-row">
                    <Checkbox
                      checked={checked}
                      onChange={(e) => {
                        const cols = wConfig.columns || [];
                        if (e.target.checked) {
                          updateConfig("columns", [
                            ...cols,
                            {
                              key: colKey,
                              label: q.label,
                              source: "answer",
                              question: q.id,
                            },
                          ]);
                        } else {
                          updateConfig(
                            "columns",
                            cols.filter((c) => c.key !== colKey)
                          );
                        }
                      }}
                    />
                    {q.label}
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* Table criteria */}
        {wType === "table" && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Criteria (filter rows)
            </label>
            {(wConfig.criteria || []).map((crit, idx) => (
              <div key={idx} className="builder-inspector-criteria-row">
                <Select
                  value={crit.type || "option_equals"}
                  onChange={(val) => {
                    const updated = [...(wConfig.criteria || [])];
                    updated[idx] = { ...updated[idx], type: val };
                    updateConfig("criteria", updated);
                  }}
                  size="small"
                  style={{ width: 130 }}
                >
                  {VALID_CRITERIA_TYPES.map((ct) => (
                    <Select.Option key={ct.value} value={ct.value}>
                      {ct.label}
                    </Select.Option>
                  ))}
                </Select>
                <Select
                  value={crit.question || null}
                  onChange={(val) => {
                    const updated = [...(wConfig.criteria || [])];
                    updated[idx] = { ...updated[idx], question: val };
                    updateConfig("criteria", updated);
                  }}
                  placeholder="Question"
                  size="small"
                  style={{ flex: 1 }}
                  allowClear
                >
                  {questionsForForm(widget.form).map((q) => (
                    <Select.Option key={q.id} value={q.id}>
                      {q.label}
                    </Select.Option>
                  ))}
                </Select>
                <Input
                  value={crit.value || ""}
                  onChange={(e) => {
                    const updated = [...(wConfig.criteria || [])];
                    updated[idx] = { ...updated[idx], value: e.target.value };
                    updateConfig("criteria", updated);
                  }}
                  placeholder="Value"
                  size="small"
                  style={{ width: 90 }}
                />
                <button
                  className="builder-inspector-criteria-remove"
                  title="Remove condition"
                  aria-label="Remove condition"
                  onClick={() => {
                    const updated = (wConfig.criteria || []).filter(
                      (_, i) => i !== idx
                    );
                    updateConfig("criteria", updated);
                  }}
                >
                  <DeleteOutlined />
                </button>
              </div>
            ))}
            <button
              className="builder-inspector-add-btn"
              onClick={() => {
                updateConfig("criteria", [
                  ...(wConfig.criteria || []),
                  { type: "option_equals", question: null, value: "" },
                ]);
              }}
            >
              + Add criterion
            </button>
          </div>
        )}

        {/* Table row limit */}
        {wType === "table" && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Rows to show</label>
            <InputNumber
              value={wConfig.page_size || 20}
              min={1}
              max={100}
              step={5}
              style={{ width: "100%" }}
              onChange={(val) => {
                // Reaches /escalation as `page_size` and Ant's pagination as
                // the page length, so one control governs both how much is
                // fetched and how much is drawn. Clamped to the serializer's
                // own bounds rather than sending a value it would reject.
                updateConfig("page_size", val || 20);
              }}
            />
            <div className="builder-inspector-hint">
              Rows per page, up to 100.
            </div>
          </div>
        )}

        {/* Map status colours */}
        {wType === "map" && widget.question && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Status colours</label>
            {(selectedQuestion?.options || []).map((opt) => {
              const colors = wConfig.status_colors || {};
              return (
                <div
                  key={opt.value}
                  className="builder-inspector-status-color-row"
                >
                  <span>{opt.label}</span>
                  <input
                    type="color"
                    value={colors[opt.value] || "#64A73B"}
                    onChange={(e) => {
                      updateConfig("status_colors", {
                        ...colors,
                        [opt.value]: e.target.value,
                      });
                    }}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* Accent colour */}
        {NEEDS_COLOR.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Accent colour</label>
            <div className="builder-inspector-swatches">
              {COLOR_SWATCHES.map((c) => (
                <button
                  key={c}
                  className={`builder-swatch${
                    widget.color === c ? " builder-swatch--active" : ""
                  }`}
                  style={{ background: c }}
                  onClick={() => updateWidget("color", c)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Width */}
        <div className="builder-inspector-field">
          <label className="builder-inspector-label">Width</label>
          <div className="builder-inspector-widths">
            {WIDTH_PRESETS.map((wp) => (
              <button
                key={wp.col_span}
                className={`builder-width-btn${
                  widget.col_span === wp.col_span
                    ? " builder-width-btn--active"
                    : ""
                }`}
                onClick={() => updateWidget("col_span", wp.col_span)}
              >
                <span className="builder-width-frac">{wp.frac}</span>
                <span className="builder-width-label">{wp.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

BuilderInspector.propTypes = {
  widget: PropTypes.object,
  sources: PropTypes.object,
  dashboardName: PropTypes.string,
  dashboardDesc: PropTypes.string,
  defaultFilters: PropTypes.object,
  onWidgetChange: PropTypes.func.isRequired,
  onDashboardChange: PropTypes.func.isRequired,
  errorMessage: PropTypes.string,
};

export default BuilderInspector;
