import React from "react";
import PropTypes from "prop-types";
import { Popover, Space, Tag, Tooltip } from "antd";
import { CloseOutlined, InfoCircleOutlined } from "@ant-design/icons";
import Overflow from "rc-overflow";
import { filterKey } from "../../util/dashboardGlobalFilter";

// =========================================================
// The applied question filters, as chips (VIZ-027)
// =========================================================
//
// A section of its own under the filter bar: one chip per applied value,
// as the WAI portal draws them: the option, with an info icon whose
// tooltip names the question ("Yes" alone does not say what it answers),
// so a chip stays short. Closing a chip removes
// that value at once, as the WAI portal's tags do. The row is one line:
// what does not fit collapses into "+N", whose popover (hover or click)
// lists the rest, each still removable. rc-overflow measures the row; it
// is what antd's own `maxTagCount="responsive"` is built on.

const keyOf = (question) => filterKey(question.form, question.name);

// Applied values, in the options' order, of questions that still offer
// them: what the panel shows as ticked (QuestionFilters). Also the
// export's filter summary (ExportFilterSummary).
export const appliedItems = (questions, selections) =>
  questions.flatMap((question) => {
    const ticked = selections?.[keyOf(question)] || [];
    return (question.options || [])
      .filter((option) => ticked.includes(option.value))
      .map((option) => ({
        key: `${keyOf(question)}:${option.value}`,
        question,
        value: option.value,
        label: option.label || option.value,
      }));
  });

const ActiveFilterChips = ({
  questions,
  value,
  onChange,
  disabled,
  text,
  maxCount = "responsive",
}) => {
  const items = appliedItems(questions, value.selections);
  if (!items.length) {
    return null;
  }

  const remove = (item) => {
    const key = keyOf(item.question);
    const next = { ...value.selections };
    const kept = (next[key] || []).filter((v) => v !== item.value);
    if (kept.length) {
      next[key] = kept;
    } else {
      delete next[key];
    }
    onChange({
      ...value,
      selections: next,
      // "Any" means nothing with fewer than two filters.
      match: Object.keys(next).length > 1 ? value.match : "all",
    });
  };

  const chip = (item) => (
    <Tooltip key={item.key} title={item.question.label}>
      <Tag
        className="dashboard-question-filter-chip"
        data-testid={`question-filter-chip-${item.key}`}
        icon={
          <InfoCircleOutlined
            role="img"
            tabIndex={0}
            aria-label={item.question.label}
          />
        }
        closable={!disabled}
        closeIcon={
          <CloseOutlined
            role="button"
            aria-label={`${text.dashboardFiltersRemove} ${item.question.label}: ${item.label}`}
          />
        }
        onClose={(event) => {
          // The chip goes when the state does; antd must not hide it.
          event.preventDefault();
          remove(item);
        }}
      >
        {item.label}
      </Tag>
    </Tooltip>
  );

  return (
    <div className="dashboard-view-filters-chips" aria-live="polite">
      <Overflow
        prefixCls="dashboard-filter-chips"
        data={items}
        itemKey="key"
        maxCount={maxCount}
        renderItem={chip}
        renderRest={(omitted) => (
          <Popover
            placement="bottom"
            trigger={["hover", "click"]}
            content={
              <Space wrap className="dashboard-filter-chips-more">
                {omitted.map(chip)}
              </Space>
            }
          >
            <Tag
              className="dashboard-question-filter-chip dashboard-filter-chips-rest-tag"
              data-testid="question-filter-chips-rest"
              tabIndex={0}
              role="button"
              aria-label={`+${omitted.length} ${text.dashboardFiltersMore}`}
            >
              +{omitted.length}
            </Tag>
          </Popover>
        )}
      />
    </div>
  );
};

ActiveFilterChips.propTypes = {
  questions: PropTypes.array.isRequired,
  value: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  text: PropTypes.object.isRequired,
  // "responsive" in the app; a number in tests, where nothing is measured.
  maxCount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export default ActiveFilterChips;
