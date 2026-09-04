import React, { useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import { Input, InputNumber, Select, Switch, Checkbox } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import DashboardVisibilityToggle from "./DashboardVisibilityToggle";
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
  COLOR_SCHEMES,
  DEFAULT_COLOR_SCHEME,
  TYPE_LABELS,
  NEEDS_SCATTER_Y,
  defaultMeasure,
  pruneConfigForForm,
  tableColumnOptions,
  monitoringForms,
} from "./builderConstants";

const { TextArea } = Input;

/* IBM Carbon-style icons, same as akvo-react-form's svgIcons.js */
const ICON_SIZE = 16;

const IconNumber = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="2 8 28 18">
    <path
      fill="currentColor"
      d="M26 12h-4v2h4v2h-3v2h3v2h-4v2h4a2.003 2.003 0 0 0 2-2v-6a2.002 2.002 0 0 0-2-2zm-7 10h-6v-4a2.002 2.002 0 0 1 2-2h2v-2h-4v-2h4a2.002 2.002 0 0 1 2 2v2a2.002 2.002 0 0 1-2 2h-2v2h4zM8 20v-8H6v1H4v2h2v5H4v2h6v-2H8z"
    />
  </svg>
);

const IconText = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 6 32 18">
    <path
      fill="currentColor"
      d="M29 22h-5a2.003 2.003 0 0 1-2-2v-6a2.002 2.002 0 0 1 2-2h5v2h-5v6h5zM18 12h-4V8h-2v14h6a2.003 2.003 0 0 0 2-2v-6a2.002 2.002 0 0 0-2-2zm-4 8v-6h4v6zm-6-8H3v2h5v2H4a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h6v-8a2.002 2.002 0 0 0-2-2zm0 8H4v-2h4z"
    />
  </svg>
);

const IconOption = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 32 32">
    <path
      fill="currentColor"
      d="M16 2a14 14 0 1 0 14 14A14 14 0 0 0 16 2zm0 26a12 12 0 1 1 12-12 12 12 0 0 1-12 12z"
    />
    <circle cx="16" cy="16" r="6" fill="currentColor" />
  </svg>
);

const IconCheckbox = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 32 32">
    <path
      fill="currentColor"
      d="M26 4H6a2 2 0 0 0-2 2v20a2 2 0 0 0 2 2h20a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM6 26V6h20v20z"
    />
    <path
      fill="currentColor"
      d="m14 21.5-5-4.96 1.59-1.57L14 18.35 21.41 11 23 12.58l-9 8.92z"
    />
  </svg>
);

const IconDate = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 32 32">
    <path
      fill="currentColor"
      d="M26 4h-4V2h-2v2h-8V2h-2v2H6a2 2 0 0 0-2 2v20a2 2 0 0 0 2 2h20a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 22H6V12h20zm0-16H6V6h4v2h2V6h8v2h2V6h4z"
    />
  </svg>
);

const QUESTION_TYPE_ICON = {
  number: <IconNumber />,
  option: <IconOption />,
  multiple_option: <IconCheckbox />,
  date: <IconDate />,
};

const QuestionLabel = ({ label, type }) => (
  <span className="builder-inspector-q-label">
    {QUESTION_TYPE_ICON[type] || <IconText />}
    {label}
  </span>
);

const BuilderInspector = ({
  widget,
  sources,
  dashboardName,
  dashboardDesc,
  defaultFilters,
  isPublic,
  isPublished,
  onWidgetChange,
  onDashboardChange,
  onVisibilityChange,
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
              Date
              <Switch
                size="small"
                checked={Boolean(defaultFilters?.date?.enabled)}
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
                checked={Boolean(defaultFilters?.administration?.enabled)}
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

          <DashboardVisibilityToggle
            isPublic={isPublic}
            isPublished={isPublished}
            onChange={onVisibilityChange}
          />

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
  const allQuestions = showQuestion ? questionsForForm(widget.form) : [];
  const questions =
    wType === "scatter"
      ? allQuestions.filter((q) => q.type === "number")
      : allQuestions;
  const selectedQuestion = allQuestions.find((q) => q.id === widget.question);
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
                  wType === "table"
                    ? tableColumnOptions(forms, val).map((o) => ({
                        id: o.question,
                      }))
                    : questionsForForm(val)
                );
                const nextConfig = {
                  ...pruned,
                  measure: supported
                    ? widget.config?.measure || supported
                    : null,
                };
                if (wType === "scatter") {
                  nextConfig.question_y = null;
                  nextConfig.x_axis_label = null;
                  nextConfig.y_axis_label = null;
                }
                onWidgetChange({
                  ...widget,
                  form: val,
                  question: null,
                  config: nextConfig,
                });
              }}
              placeholder="Select a form"
              style={{ width: "100%" }}
              allowClear
            >
              {(wType === "table" ? monitoringForms(forms) : forms).map((f) => (
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
              {wType === "map"
                ? "Status question"
                : wType === "scatter"
                ? "X axis (number question)"
                : "Question"}
            </label>
            <Select
              value={widget.question || null}
              onChange={(val) => {
                if (wType === "map" && val) {
                  const q = questions.find((qq) => qq.id === val);
                  const sc =
                    COLOR_SCHEMES[wConfig.color_scheme || DEFAULT_COLOR_SCHEME];
                  const auto = {};
                  (q?.options || []).forEach((opt, idx) => {
                    auto[opt.value] = sc.colors[idx % sc.colors.length];
                  });
                  onWidgetChange({
                    ...widget,
                    question: val,
                    config: { ...widget.config, status_colors: auto },
                  });
                } else if (wType === "scatter") {
                  const q = questions.find((qq) => qq.id === val);
                  onWidgetChange({
                    ...widget,
                    question: val || null,
                    config: {
                      ...widget.config,
                      x_axis_label: q?.label || null,
                    },
                  });
                } else {
                  updateWidget("question", val);
                }
              }}
              placeholder={
                wType === "scatter"
                  ? "Number of datapoints"
                  : "Select a question"
              }
              style={{ width: "100%" }}
              allowClear
              optionLabelProp="label"
            >
              {questions.map((q) => (
                <Select.Option
                  key={q.id}
                  value={q.id}
                  label={<QuestionLabel label={q.label} type={q.type} />}
                >
                  <QuestionLabel label={q.label} type={q.type} />
                </Select.Option>
              ))}
            </Select>
            {wType === "scatter" && !widget.question && (
              <div className="builder-inspector-hint">
                Default: each datapoint counts as 1
              </div>
            )}
          </div>
        )}

        {/* Scatter Y axis */}
        {NEEDS_SCATTER_Y.has(wType) && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Y axis (number question)
            </label>
            <Select
              value={wConfig.question_y || null}
              onChange={(val) => {
                const q = questions.find((qq) => qq.id === val);
                onWidgetChange({
                  ...widget,
                  config: {
                    ...widget.config,
                    question_y: val || null,
                    y_axis_label: q?.label || null,
                  },
                });
              }}
              placeholder="Number of datapoints"
              style={{ width: "100%" }}
              allowClear
              optionLabelProp="label"
            >
              {questions.map((q) => (
                <Select.Option
                  key={q.id}
                  value={q.id}
                  label={<QuestionLabel label={q.label} type={q.type} />}
                >
                  <QuestionLabel label={q.label} type={q.type} />
                </Select.Option>
              ))}
            </Select>
            {!wConfig.question_y && (
              <div className="builder-inspector-hint">
                Default: each datapoint counts as 1
              </div>
            )}
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
              {/* Question columns, from both sides of the join */}
              {tableColumnOptions(forms, widget.form).map((opt) => {
                const checked = (wConfig.columns || []).some(
                  (c) => c.key === opt.key
                );
                return (
                  <label key={opt.key} className="builder-inspector-col-row">
                    <Checkbox
                      checked={checked}
                      onChange={(e) => {
                        const cols = wConfig.columns || [];
                        if (e.target.checked) {
                          updateConfig("columns", [
                            ...cols,
                            {
                              key: opt.key,
                              label: opt.label,
                              source: opt.source,
                              question: opt.question,
                            },
                          ]);
                        } else {
                          updateConfig(
                            "columns",
                            cols.filter((c) => c.key !== opt.key)
                          );
                        }
                      }}
                    />
                    <span>
                      {opt.label}
                      <span className="builder-inspector-col-form">
                        {opt.formName}
                      </span>
                    </span>
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

        {/* Colour scheme */}
        {NEEDS_COLOR.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Colour scheme</label>
            <div className="builder-inspector-schemes">
              {Object.entries(COLOR_SCHEMES).map(([key, scheme]) => (
                <button
                  key={key}
                  className={`builder-scheme${
                    (wConfig.color_scheme || DEFAULT_COLOR_SCHEME) === key
                      ? " builder-scheme--active"
                      : ""
                  }`}
                  title={scheme.label}
                  onClick={() => {
                    const next = {
                      ...widget.config,
                      color_scheme: key,
                      chart_colors: scheme.colors,
                    };
                    if (wType === "map" && widget.question) {
                      const opts = selectedQuestion?.options || [];
                      const auto = {};
                      opts.forEach((opt, idx) => {
                        auto[opt.value] =
                          scheme.colors[idx % scheme.colors.length];
                      });
                      next.status_colors = auto;
                    }
                    onWidgetChange({ ...widget, config: next });
                  }}
                >
                  {scheme.colors.map((c) => (
                    <span
                      key={c}
                      className="builder-scheme-dot"
                      style={{ background: c }}
                    />
                  ))}
                  <span className="builder-scheme-label">{scheme.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Per-category colours (bar/pie/line with option question) */}
        {hasOptionQuestion &&
          ["bar", "pie", "line"].includes(wType) &&
          wConfig.group_by === "option" && (
            <div className="builder-inspector-field">
              <label className="builder-inspector-label">
                Category colours
              </label>
              {(selectedQuestion?.options || []).map((opt, idx) => {
                const overrides = wConfig.option_colors || {};
                const scheme =
                  COLOR_SCHEMES[wConfig.color_scheme || DEFAULT_COLOR_SCHEME];
                const defaultColor = scheme.colors[idx % scheme.colors.length];
                return (
                  <div
                    key={opt.value}
                    className="builder-inspector-status-color-row"
                  >
                    <span>{opt.label}</span>
                    <input
                      type="color"
                      value={overrides[opt.label] || defaultColor}
                      onChange={(e) => {
                        updateConfig("option_colors", {
                          ...overrides,
                          [opt.label]: e.target.value,
                        });
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}

        {/* Map status colours */}
        {wType === "map" && widget.question && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Status colours</label>
            {(selectedQuestion?.options || []).map((opt, idx) => {
              const colors = wConfig.status_colors || {};
              const scheme =
                COLOR_SCHEMES[wConfig.color_scheme || DEFAULT_COLOR_SCHEME];
              const defaultColor = scheme.colors[idx % scheme.colors.length];
              return (
                <div
                  key={opt.value}
                  className="builder-inspector-status-color-row"
                >
                  <span>{opt.label}</span>
                  <input
                    type="color"
                    value={colors[opt.value] || defaultColor}
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
  isPublic: PropTypes.bool,
  isPublished: PropTypes.bool,
  onWidgetChange: PropTypes.func.isRequired,
  onDashboardChange: PropTypes.func.isRequired,
  onVisibilityChange: PropTypes.func,
  errorMessage: PropTypes.string,
};

export default BuilderInspector;
