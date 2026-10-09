import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Checkbox, Empty, Input, Modal, Select, Tag } from "antd";
import { filterKey } from "../../util/dashboardGlobalFilter";

// =========================================================
// Builder: choose the filter bar's questions, in a modal (VIZ-027)
// =========================================================
//
// The inspector is too narrow to tell questions apart: the same label can
// sit in two question groups (a borehole's and a desalination plant's
// "Type of Power Supply"). Here each question shows under its group, with
// its name and options. One scope at a time: "All forms" (the family, by
// name) or one monitoring form. Ticks are a draft until Apply.

const keyOf = (entry) => filterKey(entry.form, entry.name);

const matches = (entry, search) =>
  !search ||
  [entry.label, entry.name, entry.group]
    .filter(Boolean)
    .some((s) => s.toLowerCase().includes(search));

// Sections in the forms' order: the widgets' questions first (D-17), then
// one per question group.
const sectionsOf = (entries, suggestedTitle) => {
  const suggested = entries.filter((entry) => entry.suggested);
  const groups = entries
    .filter((entry) => !entry.suggested)
    .reduce((acc, entry) => {
      const title = entry.groupForm
        ? `${entry.group} — ${entry.groupForm}`
        : entry.group;
      const section = acc.find((s) => s.title === title);
      if (section) {
        section.entries.push(entry);
      } else {
        acc.push({ title, entries: [entry] });
      }
      return acc;
    }, []);
  return [
    suggested.length && { title: suggestedTitle, entries: suggested },
    ...groups,
  ].filter(Boolean);
};

// Mounted only while open, so every opening starts from the saved value.
const DashboardQuestionFilterModal = ({
  entries,
  scopes,
  value,
  onApply,
  onCancel,
  text,
}) => {
  const [draft, setDraft] = useState(value);
  const [scope, setScope] = useState(scopes[0]?.value);
  const [search, setSearch] = useState("");

  const picked = new Set(draft.map(keyOf));
  const sections = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return sectionsOf(
      entries.filter((entry) => entry.form === scope && matches(entry, needle)),
      text.dashboardFilterSuggested
    );
  }, [entries, scope, search, text.dashboardFilterSuggested]);

  const toggle = (entry, checked) =>
    setDraft(
      checked
        ? [...draft, { form: entry.form, name: entry.name }]
        : draft.filter((e) => keyOf(e) !== keyOf(entry))
    );

  return (
    <Modal
      visible
      width={760}
      title={`${text.dashboardFilterQuestions} · ${draft.length} ${text.dashboardFilterSelected}`}
      okText={text.dashboardFiltersApply}
      cancelText={text.cancelButton}
      onOk={() => onApply(draft)}
      onCancel={onCancel}
      className="builder-question-filter-modal"
    >
      <div className="builder-question-filter-modal-tools">
        <Select
          aria-label={text.dashboardFilterScope}
          value={scope}
          options={scopes}
          onChange={setScope}
          virtual={false}
        />
        <Input.Search
          allowClear
          aria-label={text.dashboardFilterSearch}
          placeholder={text.dashboardFilterSearch}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div className="builder-question-filter-modal-list">
        {!sections.length && (
          <Empty description={text.dashboardFilterNoMatch} />
        )}
        {sections.map((section) => (
          <section key={section.title} aria-label={section.title}>
            <h4>{section.title}</h4>
            {section.entries.map((entry) => (
              <label
                key={keyOf(entry)}
                className="builder-question-filter-option"
                data-testid={`question-filter-option-${keyOf(entry)}`}
              >
                <Checkbox
                  checked={picked.has(keyOf(entry))}
                  onChange={(event) => toggle(entry, event.target.checked)}
                />
                <span className="builder-question-filter-option-body">
                  <span className="builder-question-filter-option-label">
                    {entry.label}
                    {entry.suggested && (
                      <Tag className="builder-question-filter-option-group">
                        {entry.group}
                      </Tag>
                    )}
                  </span>
                  <span className="builder-question-filter-option-meta">
                    <code>{entry.name}</code>
                    {" · "}
                    {entry.options.map((o) => o.label || o.value).join(", ")}
                  </span>
                  {entry.covers && (
                    <span className="builder-question-filter-option-meta">
                      {text.dashboardFilterCovers} {entry.covers}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </section>
        ))}
      </div>
    </Modal>
  );
};

DashboardQuestionFilterModal.propTypes = {
  entries: PropTypes.array.isRequired,
  scopes: PropTypes.array.isRequired,
  value: PropTypes.array.isRequired,
  onApply: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  text: PropTypes.object.isRequired,
};

export default DashboardQuestionFilterModal;
