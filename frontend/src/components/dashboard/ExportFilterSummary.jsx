import React from "react";
import PropTypes from "prop-types";
import { appliedItems } from "./ActiveFilterChips";

// =========================================================
// The active filters, in words, for the export only (VIZ-027)
// =========================================================
//
// The filter bar is controls, which mean nothing on paper, so the export
// leaves it out (`data-html2canvas-ignore`). A filtered export must still
// say it is filtered, or its numbers read as the whole: this line takes
// the bar's place. Hidden on screen (`.dashboard-export-only`), shown by
// dashboardExport's `showExportOnly` in the copy it draws. Nothing
// active, nothing rendered: an unfiltered export has no filter line.

const ExportFilterSummary = ({
  questions,
  value,
  administrationName,
  text,
}) => {
  const groups = appliedItems(questions, value.selections).reduce(
    (acc, item) => {
      const group = acc.find((g) => g.question === item.question);
      if (group) {
        group.labels.push(item.label);
      } else {
        acc.push({ question: item.question, labels: [item.label] });
      }
      return acc;
    },
    []
  );
  const parts = [
    (value.from_date || value.to_date) &&
      `${text.dashboardFilterPeriod}: ${value.from_date || "…"} – ${
        value.to_date || "…"
      }`,
    value.administration_id &&
      administrationName &&
      `${text.dashboardFilterLocation}: ${administrationName}`,
    ...groups.map((g) => `${g.question.label}: ${g.labels.join(", ")}`),
    groups.length > 1 &&
      value.match === "any" &&
      `${text.dashboardFiltersMatch}: ${text.dashboardFiltersMatchAny}`,
  ].filter(Boolean);

  if (!parts.length) {
    return null;
  }
  return (
    <div
      className="dashboard-export-only dashboard-export-filters"
      data-testid="export-filter-summary"
    >
      <strong>{text.dashboardExportFiltered}</strong> {parts.join(" · ")}
    </div>
  );
};

ExportFilterSummary.propTypes = {
  questions: PropTypes.array.isRequired,
  value: PropTypes.object.isRequired,
  administrationName: PropTypes.string,
  text: PropTypes.object.isRequired,
};

export default ExportFilterSummary;
