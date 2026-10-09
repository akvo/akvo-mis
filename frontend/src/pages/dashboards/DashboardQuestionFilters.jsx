import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Button } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { store, uiText } from "../../lib";
import { filterKey } from "../../util/dashboardGlobalFilter";
import DashboardQuestionFilterModal from "./DashboardQuestionFilterModal";

// =========================================================
// Builder: which filters the published filter bar offers (VIZ-027)
// =========================================================
//
// A filter is a question NAME with a scope (D-20), saved as
// `default_filters.questions[] = {form, name}`:
//   - "All forms": the registration form's id. The filter reads the
//     latest answer to that name on every form of the family that asks it.
//   - One monitoring form: that form only.
// Questions the widgets on the canvas use are offered first, but every
// option question of the family stays available (D-17): filtering on a
// question no widget shows is the main use case. They are chosen in a
// modal (DashboardQuestionFilterModal): the inspector is too narrow to
// show the question groups that tell same-labelled questions apart.

const OPTION_TYPES = ["option", "multiple_option"];

// The config keys that name a question (useWidgetData's request builders).
const WIDGET_QUESTION_KEYS = [
  "question_y",
  "stack_question",
  "category_question_id",
  "value_question",
];

const widgetQuestionIds = (widgets) =>
  (widgets || []).reduce((ids, widget) => {
    const config = widget?.config || {};
    [
      widget?.question,
      ...WIDGET_QUESTION_KEYS.map((key) => config[key]),
      ...(config.criteria || []).map((c) => c?.question),
      ...(config.columns || []).map((c) => c?.question),
    ]
      .filter(Boolean)
      .forEach((id) => ids.add(id));
    return ids;
  }, new Set());

// Every option question of the family, with its form.
const optionQuestions = (forms) =>
  forms.flatMap((form) =>
    (form.questions || [])
      .filter(
        (q) =>
          OPTION_TYPES.includes(q.type) &&
          typeof q.name === "string" &&
          q.name &&
          !q.name.includes(":")
      )
      .map((q) => ({ ...q, form }))
  );

// What the picker can offer: one "All forms" entry per name, labelled by
// the registration form's question if it asks it, else the first form's;
// and one entry per monitoring form asking it. Each carries its question
// group, options and whether a widget uses it (D-17), for the modal.
const offeredEntries = (forms, rootId, allFormsLabel, usedIds) => {
  const questions = optionQuestions(forms);
  const byName = questions.reduce((acc, q) => {
    acc[q.name] = acc[q.name] || [];
    acc[q.name].push(q);
    return acc;
  }, {});
  const family = Object.entries(byName).map(([name, group]) => {
    const own = group.find((q) => q.form.id === rootId) || group[0];
    return {
      form: rootId,
      name,
      label: own.label,
      scope: allFormsLabel,
      group: own.group,
      groupForm: own.form.id === rootId ? null : own.form.name,
      options: own.options || [],
      covers: group.map((q) => q.form.name).join(", "),
      suggested: group.some((q) => usedIds.has(q.id)),
    };
  });
  const perForm = questions
    .filter((q) => q.form.id !== rootId)
    .map((q) => ({
      form: q.form.id,
      name: q.name,
      label: q.label,
      scope: q.form.name,
      group: q.group,
      options: q.options || [],
      suggested: usedIds.has(q.id),
    }));
  return { family, perForm, byName };
};

const titleOf = (entry) => `${entry.label} — ${entry.scope}`;

// Values not asked on every form an "All forms" entry covers (D-14).
const mismatches = (group) => {
  const formsByValue = new Map();
  group.forEach((q) =>
    (q.options || []).forEach((option) => {
      const seen = formsByValue.get(option.value) || {
        label: option.label,
        forms: [],
      };
      seen.forms.push(q.form.name);
      formsByValue.set(option.value, seen);
    })
  );
  return Array.from(formsByValue.values()).filter(
    (seen) => seen.forms.length < group.length
  );
};

const DashboardQuestionFilters = ({ sources, widgets, value, onChange }) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];
  const forms = useMemo(() => sources?.forms || [], [sources]);
  const rootId = forms.find((f) => !f.parent)?.id;

  const { family, perForm, byName } = useMemo(
    () =>
      offeredEntries(
        forms,
        rootId,
        text.dashboardFilterAllForms,
        widgetQuestionIds(widgets)
      ),
    [forms, rootId, text.dashboardFilterAllForms, widgets]
  );
  const scopes = [
    { value: rootId, label: text.dashboardFilterAllForms },
    ...forms
      .filter((f) => f.id !== rootId && perForm.some((e) => e.form === f.id))
      .map((f) => ({ value: f.id, label: f.name })),
  ];
  const [open, setOpen] = useState(false);

  const describe = (entry) =>
    [...family, ...perForm].find(
      (e) => e.form === entry.form && e.name === entry.name
    );

  return (
    <div className="builder-question-filters">
      <div className="builder-inspector-sublabel">
        {text.dashboardFilterQuestions}
      </div>
      {value.map((entry) => {
        const known = describe(entry);
        const isFamily = entry.form === rootId;
        const group = isFamily ? byName[entry.name] || [] : [];
        const missing = isFamily ? mismatches(group) : [];
        return (
          <div
            key={filterKey(entry.form, entry.name)}
            className="builder-question-filter-entry"
            data-testid={`question-filter-entry-${entry.form}-${entry.name}`}
          >
            <div className="builder-question-filter-head">
              <span>
                {known
                  ? titleOf(known)
                  : `${entry.name} ${text.dashboardFilterGone}`}
              </span>
              <Button
                size="small"
                type="text"
                icon={<DeleteOutlined />}
                aria-label={`${text.dashboardFilterRemove} ${
                  known ? titleOf(known) : entry.name
                }`}
                onClick={() => onChange(value.filter((e) => e !== entry))}
              />
            </div>
            {known?.group && (
              <div className="builder-question-filter-covers">
                {known.group}
              </div>
            )}
            {isFamily && group.length > 0 && (
              <div className="builder-question-filter-covers">
                {text.dashboardFilterCovers}{" "}
                {group.map((q) => q.form.name).join(", ")}
              </div>
            )}
            {missing.length > 0 && (
              <div className="builder-question-filter-warning" role="alert">
                {missing
                  .map(
                    (seen) =>
                      `${seen.label}: ${
                        text.dashboardFilterOnlyOn
                      } ${seen.forms.join(", ")}`
                  )
                  .join("; ")}
              </div>
            )}
          </div>
        );
      })}
      <Button
        block
        className="builder-question-filter-choose"
        onClick={() => setOpen(true)}
        disabled={!family.length}
      >
        {text.dashboardFilterChoose}
      </Button>
      {open && (
        <DashboardQuestionFilterModal
          entries={[...family, ...perForm]}
          scopes={scopes}
          value={value}
          text={text}
          onCancel={() => setOpen(false)}
          onApply={(next) => {
            onChange(next);
            setOpen(false);
          }}
        />
      )}
    </div>
  );
};

DashboardQuestionFilters.propTypes = {
  sources: PropTypes.shape({ forms: PropTypes.array }),
  widgets: PropTypes.array,
  value: PropTypes.arrayOf(
    PropTypes.shape({ form: PropTypes.number, name: PropTypes.string })
  ).isRequired,
  onChange: PropTypes.func.isRequired,
};

export default DashboardQuestionFilters;
