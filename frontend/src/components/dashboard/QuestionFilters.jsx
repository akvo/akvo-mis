import React, { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Badge, Button, Checkbox, Popover, Radio, Space } from "antd";
import { FilterOutlined } from "@ant-design/icons";
import {
  MAX_GLOBAL_CRITERIA,
  filterKey,
  serializeGlobalCriteria,
} from "../../util/dashboardGlobalFilter";

// =========================================================
// The "Filters" panel of the dashboard filter bar (VIZ-027)
// =========================================================
//
// One checklist per question the author offers (the published
// snapshot's default_filters.questions). Nothing is ticked at first: no
// filter. Ticking options shows only the data whose latest answer is one
// of them, as in the WAI portal (D-16, D-21): the ticked values become
// `option_in` filters. A question with nothing ticked filters nothing.
//
// Ticks edit a draft; Apply emits once, so ticking three boxes reloads
// the charts once. Closing without Apply (the button again, a click
// outside, Escape) drops the draft.
//
// Only questions with options can be filtered. The builder's canvas and
// preview pass the SAVED entries ({form, name}, no options): there the
// button shows, disabled, as the viewer will see it.

const allValues = (question) => (question.options || []).map((o) => o.value);

const keyOf = (question) => filterKey(question.form, question.name);

// The ticks the panel shows: the applied selection, or nothing.
const ticksFrom = (questions, selections) =>
  Object.fromEntries(
    questions.map((question) => [
      keyOf(question),
      selections?.[keyOf(question)] || [],
    ])
  );

// Back to the state shape: only questions with something ticked, their
// ticked values in the options' order (values no longer offered drop).
const selectionsFrom = (questions, ticks) =>
  questions.reduce((acc, question) => {
    const ticked = ticks[keyOf(question)] || [];
    const kept = allValues(question).filter((v) => ticked.includes(v));
    if (kept.length) {
      acc[keyOf(question)] = kept;
    }
    return acc;
  }, {});

const sameSelections = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const QuestionFilters = ({ questions, value, onChange, disabled, text }) => {
  const [open, setOpen] = useState(false);
  const [ticks, setTicks] = useState({});
  const [match, setMatch] = useState("all");
  const panelRef = useRef(null);

  const usable = questions.filter((question) => allValues(question).length);
  const inactive = disabled || usable.length === 0;

  const applied = selectionsFrom(usable, ticksFrom(usable, value.selections));
  const appliedMatch = value.match === "any" ? "any" : "all";
  const draft = selectionsFrom(usable, ticks);
  // The backend refuses more than 50 values per request (D-15).
  const tooMany =
    (serializeGlobalCriteria(draft)?.length || 0) > MAX_GLOBAL_CRITERIA;
  const filteredCount = Object.keys(applied).length;
  const draftCount = Object.keys(draft).length;
  const effectiveMatch = draftCount > 1 ? match : "all";
  const changed =
    !sameSelections(draft, applied) ||
    (draftCount > 1 && effectiveMatch !== appliedMatch);

  // Keyboard users land in the panel, not at the end of the page where
  // the popup is portalled.
  useEffect(() => {
    if (open) {
      const first = panelRef.current?.querySelector("input");
      if (first) {
        first.focus();
      }
    }
  }, [open]);

  const handleOpenChange = (next) => {
    if (inactive) {
      return;
    }
    if (next) {
      setTicks(ticksFrom(usable, value.selections));
      setMatch(appliedMatch);
    }
    setOpen(next);
  };

  const handleApply = () => {
    if (changed && !tooMany) {
      onChange({ ...value, selections: draft, match: effectiveMatch });
    }
    setOpen(false);
  };

  const handleClear = () => {
    if (filteredCount) {
      onChange({ ...value, selections: {}, match: "all" });
    }
    setOpen(false);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const content = (
    <div
      className="dashboard-question-filters-panel"
      ref={panelRef}
      onKeyDown={handleKeyDown}
    >
      <div className="dashboard-question-filters-body">
        {usable.map((question) => {
          const key = keyOf(question);
          const ticked = ticks[key] || [];
          return (
            <fieldset
              key={key}
              className="dashboard-question-filter"
              data-testid={`question-filter-${question.form}-${question.name}`}
            >
              <legend>{question.label}</legend>
              <Checkbox.Group
                value={ticked}
                onChange={(next) => setTicks({ ...ticks, [key]: next })}
                options={question.options.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
            </fieldset>
          );
        })}
        {draftCount > 1 && (
          <fieldset
            className="dashboard-question-filters-match"
            data-testid="question-filters-match"
          >
            <legend>{text.dashboardFiltersMatch}</legend>
            <Radio.Group
              value={match}
              onChange={(event) => setMatch(event.target.value)}
            >
              <Radio value="all">{text.dashboardFiltersMatchAll}</Radio>
              <Radio value="any">{text.dashboardFiltersMatchAny}</Radio>
            </Radio.Group>
          </fieldset>
        )}
        <p className="dashboard-question-filters-note">
          {text.dashboardFiltersHowTo}
        </p>
        {tooMany && (
          <div className="dashboard-question-filter-hint" role="alert">
            {text.dashboardFiltersTooMany.replace("{max}", MAX_GLOBAL_CRITERIA)}
          </div>
        )}
      </div>
      <Space className="dashboard-question-filters-actions">
        <Button
          data-testid="question-filters-clear"
          disabled={!filteredCount}
          onClick={handleClear}
        >
          {text.dashboardFiltersClear}
        </Button>
        <Button
          type="primary"
          data-testid="question-filters-apply"
          disabled={!changed || tooMany}
          onClick={handleApply}
        >
          {text.dashboardFiltersApply}
        </Button>
      </Space>
    </div>
  );

  const label = filteredCount
    ? `${text.dashboardFilters}, ${filteredCount} ${text.dashboardFiltersActive}`
    : text.dashboardFilters;

  const popover = (
    <Popover
      content={content}
      trigger="click"
      placement="bottomRight"
      open={open && !inactive}
      onOpenChange={handleOpenChange}
    >
      <Badge count={filteredCount} size="small">
        <Button
          type="primary"
          shape="round"
          icon={<FilterOutlined />}
          disabled={inactive}
          aria-label={label}
          aria-haspopup="dialog"
          aria-expanded={open && !inactive}
          data-testid="question-filters-button"
        >
          {text.dashboardFilters}
        </Button>
      </Badge>
    </Popover>
  );

  return popover;
};

QuestionFilters.propTypes = {
  questions: PropTypes.arrayOf(
    PropTypes.shape({
      form: PropTypes.number.isRequired,
      name: PropTypes.string.isRequired,
      label: PropTypes.string,
      options: PropTypes.arrayOf(
        PropTypes.shape({ value: PropTypes.string, label: PropTypes.string })
      ),
    })
  ).isRequired,
  value: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  text: PropTypes.object.isRequired,
};

export default QuestionFilters;
