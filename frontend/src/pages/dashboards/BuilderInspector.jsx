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
  valueTypeOptions,
  VALID_ORIENTATION,
  VALID_PIE_VARIANT,
  VALID_MEASURE,
  VALID_CRITERIA_TYPES,
  WIDTH_PRESETS,
  COLOR_SCHEMES,
  DEFAULT_COLOR_SCHEME,
  TYPE_LABELS,
  NEEDS_SCATTER_Y,
  NEEDS_LINE_DATE_X,
  NEEDS_LINE_CATEGORY,
  defaultMeasure,
  pruneConfigForForm,
  stackByOptions,
  withValidStack,
  stackValueOf,
  stackChangeOf,
  groupByOptions,
  withValidGroupBy,
  breakdownOptions,
  breakdownValueOf,
  breakdownChangeOf,
  withValidBreakdown,
  valueQuestionOptions,
  repeatAggOptions,
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

const IconSite = () => (
  <svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 32 32">
    <path
      fill="currentColor"
      d="M16 18a5 5 0 1 1 5-5 5.006 5.006 0 0 1-5 5zm0-8a3 3 0 1 0 3 3 3.003 3.003 0 0 0-3-3z"
    />
    <path
      fill="currentColor"
      d="M16 30l-8.436-9.949a35.076 35.076 0 0 1-.348-.451A10.889 10.889 0 0 1 5 13a11 11 0 0 1 22 0 10.884 10.884 0 0 1-2.215 6.597l-.001.002s-.3.394-.345.447zm-7.191-11.6c.002 0 .232.305.284.373L16 26.888l6.915-8.153c.044-.055.276-.363.278-.365A8.901 8.901 0 0 0 25 13a9 9 0 1 0-18 0 8.905 8.905 0 0 0 1.809 5.4z"
    />
  </svg>
);

// The merged Break down by list mixes questions with fixed choices, so
// the fixed ones carry a glyph of their own rather than sitting bare
// beside icons.
const BREAKDOWN_ICON = {
  date: <IconDate />,
  site: <IconSite />,
};

const QUESTION_TYPE_ICON = {
  number: <IconNumber />,
  option: <IconOption />,
  multiple_option: <IconCheckbox />,
  date: <IconDate />,
};

/** A fixed breakdown choice: its own glyph, or none for "None". */
const BreakdownLabel = ({ choice }) => (
  <span className="builder-inspector-q-label">
    {choice.type
      ? QUESTION_TYPE_ICON[choice.type] || <IconText />
      : BREAKDOWN_ICON[choice.icon] || null}
    {choice.label}
  </span>
);

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
    wType === "scatter" || wType === "line"
      ? allQuestions.filter((q) => q.type === "number")
      : allQuestions;
  const dateQuestions = allQuestions.filter((q) => q.type === "date");
  const optionQuestions = allQuestions.filter(
    (q) => q.type === "option" || q.type === "multiple_option"
  );
  const selectedQuestion = allQuestions.find((q) => q.id === widget.question);
  const selectedCategoryQuestion = allQuestions.find(
    (q) => q.id === wConfig.category_question_id
  );
  // Only bar offers the question entries. Nothing technical stops a line
  // chart on an option question from stacking the same way — /values
  // never sees the widget type — but the acceptance criteria name bar,
  // so widening this is a separate decision, not an accident.
  //
  // The grouping is passed for every type all the same: a line chart on a
  // number question stacks by site over month or date, and withholding
  // the grouping would hide that working combination too.
  const stackChoices = stackByOptions(
    allQuestions,
    widget.question,
    wConfig.group_by || "option",
    // The whole family, already in memory: /sources returns every form
    // with its questions, so the cross-form picker costs no new request.
    wType === "bar" ? forms : [],
    widget.form
  ).filter((s) => wType === "bar" || !String(s.value).startsWith("q:"));
  // Cross-form joins per site, so the grouping is derived, not chosen.
  const stackIsCrossForm = Boolean(wConfig.stack_form);

  // The number questions this bar could be measured by, and the
  // aggregations that stay honest for the split it carries.
  const valueChoices = valueQuestionOptions(allQuestions, selectedQuestion);
  const splitQuestion = wConfig.stack_question
    ? allQuestions.find((q) => q.id === wConfig.stack_question)
    : selectedQuestion;
  const aggChoices = repeatAggOptions(
    splitQuestion?.type === "multiple_option",
    Boolean(wConfig.stack_by)
  );

  // Bar's single control (S-13). Line and pie keep the pair above: a
  // line's request path fixes group_by=month and ignores the control,
  // and a pie has no stack to merge with.
  const breakdownChoices = breakdownOptions(
    selectedQuestion,
    allQuestions,
    forms,
    widget.form
  );

  // The list offers no question entries for a number question, because
  // the compute layer has no path for one: `handle_number_question`
  // routes on group_by and stack_by alone, and `stack_question_id` is
  // refused unless the measured question is option-typed. The chart is
  // not unavailable, though — it is spelled with the roles swapped, and
  // saying so is the difference between a missing feature and a
  // misunderstood one.
  const breakdownHint = (() => {
    if (breakdownChoices.length === 0) {
      return "Pick a question first";
    }
    if (selectedQuestion?.type === "number") {
      return (
        "A number question is already the measure, so it can only be" +
        " broken down by time or site. To split it by an option" +
        " question, make that the Question and set this one as the Value."
      );
    }
    return (
      "The chart's second dimension: the axis for a time or a site," +
      " the segments for another question."
    );
  })();

  // Why Percentage is not in the list, when a Value question put it
  // there. Two rules meet here and neither announces itself: a
  // percentage needs a denominator that is a total of the same quantity,
  // which only `sum` gives (D-2) — and `sum` is itself withheld from a
  // multi-choice split (D-1). Together they can make Percentage
  // UNREACHABLE, with the control simply one entry shorter and no way to
  // find out why.
  const percentageWithheld = (() => {
    if (!wConfig.value_question || wConfig.repeat_agg === "sum") {
      return null;
    }
    const splitIsMulti = splitQuestion?.type === "multiple_option";
    if (splitIsMulti && wConfig.stack_by) {
      return (
        "Percentage needs a total to divide by, which only Sum gives —" +
        " and Sum is unavailable while the segments come from a" +
        " multi-choice question, because one submission counts in" +
        " several segments at once."
      );
    }
    return (
      "Percentage needs Sum: each bar's segments divide by that bar's" +
      " own total, and a total of averages is not a quantity."
    );
  })();

  // Which groupings draw at all, given the question and the stack.
  const groupChoices = groupByOptions(selectedQuestion, wConfig);
  // Hidden when there was never a choice to make — an unstacked option
  // question has exactly one way to draw, and a control with one entry
  // teaches nothing. Distinct from the cross-form case below, which
  // DISABLES rather than hides: there a choice was taken away by
  // something the author did, and that needs saying.
  //
  // Still shown when the stored value is not among the valid ones, so a
  // widget saved with a grouping that draws nothing stays repairable —
  // one click, and then it hides.
  const groupByIsForced =
    // A cross-form stack keeps its control visible and disabled instead:
    // there the author's own choice fixed the grouping, and that has a
    // cause worth stating. Hiding is for when there was never a choice.
    !stackIsCrossForm &&
    groupChoices.length <= 1 &&
    groupChoices.some((g) => g.value === (wConfig.group_by || "option"));
  // Everything a cross-form stack needs is in place EXCEPT a single-choice
  // measured question. Without saying so the entries simply are not there,
  // which reads as the feature being missing rather than unavailable —
  // the same invisible constraint D-5 was written about.
  const crossFormWithheld =
    wType === "bar" &&
    (wConfig.group_by || "option") === "parent_id" &&
    selectedQuestion?.type === "multiple_option" &&
    forms.some((f) => f.id !== widget.form);
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
                if (wType === "line") {
                  nextConfig.date_question_id = null;
                  nextConfig.category_question_id = null;
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
                disabled={Boolean(wConfig.value_question)}
                onChange={(checked) => {
                  updateConfig("include_unmonitored", checked);
                }}
              />
            </label>
            {wConfig.value_question && (
              <div className="builder-inspector-hint">
                Unavailable while the bars carry a Value: the bucket counts
                sites, and these bars are totals.
              </div>
            )}
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
                : wType === "line"
                ? "Y axis (number question)"
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
                  // Which stacks are drawable depends on the question's
                  // type, so changing it can strand the current choice —
                  // clearing a number question's leftover option stack,
                  // or a stack question that just became the measured
                  // one. A stranded value is a guaranteed 400, not a
                  // cosmetic slip.
                  //
                  // The grouping is snapped FIRST: an option question
                  // swapped for a number one strands group_by=option,
                  // which draws one "Total" bar rather than erroring.
                  // The stack is then validated against the grouping
                  // that survived, not the one being replaced.
                  const nextQuestion = allQuestions.find((q) => q.id === val);
                  if (wType === "bar") {
                    // One control, so one snap: a breakdown the new
                    // question cannot draw moves to the first that it
                    // can, which for a number question means the
                    // "None — this question's options" entry it no
                    // longer has cannot survive as group_by=option.
                    onWidgetChange({
                      ...widget,
                      question: val || null,
                      config: withValidBreakdown(
                        widget.config,
                        breakdownOptions(
                          nextQuestion,
                          allQuestions,
                          forms,
                          widget.form
                        )
                      ),
                    });
                    return;
                  }
                  const grouped = withValidGroupBy(
                    widget.config,
                    groupByOptions(nextQuestion, wConfig)
                  );
                  onWidgetChange({
                    ...widget,
                    question: val || null,
                    config: withValidStack(
                      grouped,
                      stackByOptions(
                        allQuestions,
                        val,
                        grouped.group_by || "option",
                        wType === "bar" ? forms : [],
                        widget.form
                      )
                    ),
                  });
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

        {/* Value — the bar's height, when it is not a count */}
        {NEEDS_GROUP_BY.has(wType) && valueChoices.length > 0 && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Value</label>
            <Select
              value={wConfig.value_question || null}
              onChange={(val) => {
                // Percentage survives only where it still has a
                // denominator: summed bars divide by the bar's own
                // total (D-2). Under any other aggregation it would
                // divide money by submissions, so it snaps to Count
                // rather than leaving a config the endpoint refuses.
                const keepPercentage =
                  !val || widget.config?.repeat_agg === "sum";
                onWidgetChange({
                  ...widget,
                  config: {
                    ...widget.config,
                    value_question: val || null,
                    value_type: keepPercentage
                      ? widget.config?.value_type
                      : "number",
                    // Adds a bucket counting SITES to a chart of summed
                    // households, and makes the percentage denominator a
                    // site count. Cleared rather than disabled-in-place
                    // because a stored `true` is a guaranteed 400.
                    include_unmonitored: val
                      ? false
                      : widget.config?.include_unmonitored,
                  },
                });
              }}
              placeholder="Number of submissions"
              style={{ width: "100%" }}
              allowClear
              optionLabelProp="label"
            >
              {valueChoices.map((q) => (
                <Select.Option
                  key={q.value}
                  value={q.value}
                  label={<QuestionLabel label={q.label} type={q.type} />}
                >
                  <QuestionLabel label={q.label} type={q.type} />
                </Select.Option>
              ))}
            </Select>
            <div className="builder-inspector-hint">
              {wConfig.value_question
                ? "Bars show this question's total, not a count."
                : "Leave empty to count submissions."}
            </div>
          </div>
        )}

        {/* Line X axis (date question) */}
        {NEEDS_LINE_DATE_X.has(wType) && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              X axis (date question)
            </label>
            <Select
              value={wConfig.date_question_id || null}
              onChange={(val) => {
                updateConfig("date_question_id", val || null);
              }}
              placeholder="Submission date"
              style={{ width: "100%" }}
              allowClear
              optionLabelProp="label"
            >
              {dateQuestions.map((q) => (
                <Select.Option
                  key={q.id}
                  value={q.id}
                  label={<QuestionLabel label={q.label} type={q.type} />}
                >
                  <QuestionLabel label={q.label} type={q.type} />
                </Select.Option>
              ))}
            </Select>
            {!wConfig.date_question_id && (
              <div className="builder-inspector-hint">
                Default: groups by submission date
              </div>
            )}
          </div>
        )}

        {/* Line category (option question → multiple lines) */}
        {NEEDS_LINE_CATEGORY.has(wType) && widget.form && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              Category (option question)
            </label>
            <Select
              value={wConfig.category_question_id || null}
              onChange={(val) => {
                if (val) {
                  const q = allQuestions.find((qq) => qq.id === val);
                  const sc =
                    COLOR_SCHEMES[wConfig.color_scheme || DEFAULT_COLOR_SCHEME];
                  const auto = {};
                  (q?.options || []).forEach((opt, idx) => {
                    auto[opt.label] = sc.colors[idx % sc.colors.length];
                  });
                  onWidgetChange({
                    ...widget,
                    config: {
                      ...widget.config,
                      category_question_id: val,
                      category_colors: auto,
                    },
                  });
                } else {
                  onWidgetChange({
                    ...widget,
                    config: {
                      ...widget.config,
                      category_question_id: null,
                      category_colors: null,
                    },
                  });
                }
              }}
              placeholder="None (single line)"
              style={{ width: "100%" }}
              allowClear
              optionLabelProp="label"
            >
              {optionQuestions.map((q) => (
                <Select.Option
                  key={q.id}
                  value={q.id}
                  label={<QuestionLabel label={q.label} type={q.type} />}
                >
                  <QuestionLabel label={q.label} type={q.type} />
                </Select.Option>
              ))}
            </Select>
          </div>
        )}

        {/* Break down by — bar's merged Group by + Stack by (S-13) */}
        {wType === "bar" && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Break down by</label>
            <Select
              value={breakdownValueOf(wConfig)}
              onChange={(val) => {
                // Every field in ONE update: two updateConfig calls each
                // close over the same `widget`, so the second would write
                // the first's field back to its stale value.
                onWidgetChange({
                  ...widget,
                  config: {
                    ...widget.config,
                    ...breakdownChangeOf(val, selectedQuestion),
                  },
                });
              }}
              style={{ width: "100%" }}
              disabled={breakdownChoices.length === 0}
              optionLabelProp="label"
            >
              {breakdownChoices.map((c) =>
                c.options ? (
                  <Select.OptGroup key={c.label} label={c.label}>
                    {c.options.map((o) => (
                      <Select.Option
                        key={o.value}
                        value={o.value}
                        label={<QuestionLabel label={o.label} type={o.type} />}
                      >
                        <QuestionLabel label={o.label} type={o.type} />
                      </Select.Option>
                    ))}
                  </Select.OptGroup>
                ) : (
                  <Select.Option
                    key={c.value || "none"}
                    value={c.value}
                    label={<BreakdownLabel choice={c} />}
                  >
                    <BreakdownLabel choice={c} />
                  </Select.Option>
                )
              )}
            </Select>
            <div className="builder-inspector-hint">{breakdownHint}</div>
          </div>
        )}

        {/* Group by */}
        {wType !== "bar" && NEEDS_GROUP_BY.has(wType) && !groupByIsForced && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Group by</label>
            <Select
              value={wConfig.group_by || "option"}
              onChange={(val) => {
                // Regrouping can strand the stack choice too: another
                // question's options are only drawable under
                // group_by=option, and a number question stacks by site
                // only over month or date.
                onWidgetChange({
                  ...widget,
                  config: withValidStack(
                    { ...widget.config, group_by: val },
                    stackByOptions(
                      allQuestions,
                      widget.question,
                      val,
                      wType === "bar" ? forms : [],
                      widget.form
                    )
                  ),
                });
              }}
              style={{ width: "100%" }}
              // A cross-form stack joins two responses on the registration
              // datapoint, which only exists as a key under parent_id.
              // Disabled rather than hidden: an author who cannot see why
              // the grouping is fixed will assume the control is broken.
              disabled={stackIsCrossForm}
            >
              {groupChoices.map((g) => (
                <Select.Option key={g.value} value={g.value}>
                  {g.label}
                </Select.Option>
              ))}
            </Select>
            {stackIsCrossForm && (
              <div className="builder-inspector-hint">
                Fixed while stacking by another form: this chart counts
                registration sites, one per bar.
              </div>
            )}
          </div>
        )}

        {/* Stack by */}
        {wType !== "bar" && NEEDS_STACK_BY.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Stack by</label>
            <Select
              value={stackValueOf(wConfig)}
              onChange={(val) => {
                // Every field in ONE update. Two updateConfig calls would
                // each close over the same `widget`, so the second would
                // write the first's field back to its stale value.
                //
                // The stack decides what the bars may be, so the grouping
                // is snapped against the stack that just arrived: adding a
                // self-stack rules out grouping by the same options, and
                // removing one rules everything else back out.
                const stacked = {
                  ...widget.config,
                  ...stackChangeOf(val, wConfig.group_by || "option"),
                };
                onWidgetChange({
                  ...widget,
                  config: withValidGroupBy(
                    stacked,
                    groupByOptions(selectedQuestion, stacked)
                  ),
                });
              }}
              style={{ width: "100%" }}
              disabled={stackChoices.length <= 1}
              optionLabelProp="label"
            >
              {stackChoices.map((s) =>
                s.options ? (
                  <Select.OptGroup key={s.label} label={s.label}>
                    {s.options.map((o) => (
                      <Select.Option
                        key={o.value}
                        value={o.value}
                        label={<QuestionLabel label={o.label} type={o.type} />}
                      >
                        <QuestionLabel label={o.label} type={o.type} />
                      </Select.Option>
                    ))}
                  </Select.OptGroup>
                ) : (
                  <Select.Option
                    key={s.value}
                    value={s.value}
                    label={
                      s.type ? (
                        <QuestionLabel label={s.label} type={s.type} />
                      ) : (
                        s.label
                      )
                    }
                  >
                    {/* A question entry carries its type; the three fixed
                        choices do not, and must not grow a stray icon. */}
                    {s.type ? (
                      <QuestionLabel label={s.label} type={s.type} />
                    ) : (
                      s.label
                    )}
                  </Select.Option>
                )
              )}
            </Select>
            {stackChoices.length <= 1 && (
              <div className="builder-inspector-hint">
                {widget.question
                  ? "This question and grouping cannot be stacked"
                  : "Pick a question first"}
              </div>
            )}
            {crossFormWithheld && (
              <div className="builder-inspector-hint">
                To stack by another form&apos;s question, pick a single-choice
                question above. Stacking across forms counts one answer per
                site, so a multi-choice question would lose every answer after
                the first.
              </div>
            )}
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
              {valueTypeOptions(wConfig).map((v) => (
                <Select.Option key={v.value} value={v.value}>
                  {v.label}
                </Select.Option>
              ))}
            </Select>
            {percentageWithheld && (
              <div className="builder-inspector-hint">{percentageWithheld}</div>
            )}
          </div>
        )}

        {/* Repeat aggregation */}
        {NEEDS_REPEAT_AGG.has(wType) && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">
              {wConfig.value_question
                ? "Combine values by"
                : "Repeat aggregation"}
            </label>
            <Select
              value={wConfig.repeat_agg || "average"}
              onChange={(val) => {
                // Percentage is only defined here under `sum`, so
                // moving off it takes the value type with it.
                const strands =
                  wConfig.value_question &&
                  val !== "sum" &&
                  wConfig.value_type === "percentage";
                onWidgetChange({
                  ...widget,
                  config: {
                    ...widget.config,
                    repeat_agg: val,
                    ...(strands ? { value_type: "number" } : {}),
                  },
                });
              }}
              style={{ width: "100%" }}
            >
              {aggChoices.map((r) => (
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
                    if (wType === "line" && wConfig.category_question_id) {
                      const catQ = allQuestions.find(
                        (q) => q.id === wConfig.category_question_id
                      );
                      if (catQ) {
                        const auto = {};
                        (catQ.options || []).forEach((opt, idx) => {
                          auto[opt.label] =
                            scheme.colors[idx % scheme.colors.length];
                        });
                        next.category_colors = auto;
                      }
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

        {/* Line category colours */}
        {wType === "line" && selectedCategoryQuestion && (
          <div className="builder-inspector-field">
            <label className="builder-inspector-label">Category colours</label>
            {(selectedCategoryQuestion.options || []).map((opt, idx) => {
              const overrides = wConfig.category_colors || {};
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
                      updateConfig("category_colors", {
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
