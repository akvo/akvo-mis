import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { Select } from "antd";
import { store, uiText } from "../../lib";

// =========================================================
// Builder: the date the dashboard's date range uses (VIZ-027 D-18)
// =========================================================
//
// "Submission date" (the default) or a date question of the form family.
// A date question asked on several forms under one name is offered once:
// the backend matches the stored question by name on each widget's form,
// so storing the first one (registration form first, then form order) is
// enough.

const SUBMISSION = "submission";
const SAVED = "saved";

const dateGroups = (forms) =>
  forms.reduce((groups, form) => {
    (form.questions || [])
      .filter((q) => q.type === "date" && typeof q.name === "string" && q.name)
      .forEach((q) => {
        const group = groups.find((g) => g.name === q.name);
        if (group) {
          group.forms.push(form.name);
          group.ids.push(q.id);
        } else {
          groups.push({
            name: q.name,
            id: q.id,
            ids: [q.id],
            label: q.label,
            forms: [form.name],
          });
        }
      });
    return groups;
  }, []);

const DashboardDateQuestionPicker = ({ forms, value, onChange }) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];
  // `forms` is in family order: the registration form first.
  const groups = useMemo(() => dateGroups(forms), [forms]);
  const options = [
    {
      value: SUBMISSION,
      label: text.dashboardDateSubmission,
      title: text.dashboardDateSubmission,
    },
    ...groups.map((group) => {
      const title = `${group.label} — ${group.forms.join(", ")}`;
      return { value: group.id, label: title, title };
    }),
  ];
  // A stored id of any form in a group shows as that group (the backend
  // matches it by name). One in no group, such as a question replaced by
  // a form edit, shows as a saved question rather than a bare number.
  const group = groups.find((g) => g.ids.includes(value));
  const unknown = Boolean(value) && !group;
  if (unknown) {
    options.push({
      value: SAVED,
      label: text.dashboardDateSaved,
      title: text.dashboardDateSaved,
    });
  }
  let selected = SUBMISSION;
  if (group) {
    selected = group.id;
  } else if (unknown) {
    selected = SAVED;
  }

  return (
    <div
      className="builder-inspector-date-question"
      data-testid="date-question-picker"
    >
      <div className="builder-inspector-sublabel">
        {text.dashboardDateQuestion}
      </div>
      <Select
        size="small"
        value={selected}
        options={options}
        virtual={false}
        style={{ width: "100%" }}
        aria-label={text.dashboardDateQuestion}
        onChange={(next) => {
          if (next !== SAVED) {
            onChange(next === SUBMISSION ? null : next);
          }
        }}
      />
    </div>
  );
};

DashboardDateQuestionPicker.propTypes = {
  forms: PropTypes.array.isRequired,
  value: PropTypes.number,
  onChange: PropTypes.func.isRequired,
};

export default DashboardDateQuestionPicker;
