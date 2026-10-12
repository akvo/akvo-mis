import React, { useState } from "react";
import PropTypes from "prop-types";
import { DatePicker, Space } from "antd";
import { CalendarOutlined } from "@ant-design/icons";
import AdministrationDropdownLocal from "../filters/AdministrationDropdownLocal";
import QuestionFilters from "./QuestionFilters";
import ActiveFilterChips from "./ActiveFilterChips";
import ExportFilterSummary from "./ExportFilterSummary";
import { store, uiText } from "../../lib";

const { RangePicker } = DatePicker;

// =========================================================
// The dashboard filter bar (mockup index.html:378-390)
// =========================================================
//
// Two controls, each shown only when `default_filters` enables it. Their
// values merge into every widget's request, which is coherent only because
// a dashboard is bound to one form family (VIZ-001 D-3): every widget
// shares a registration form, so "this administration, this period" means
// the same thing everywhere on the page.
//
// `AdministrationDropdownLocal` rather than `AdministrationDropdown`: the
// local one owns its selection in React state instead of writing to the
// global Pullstate store. A page-scoped filter must not leak its selection
// into other screens the user navigates to next.
//
// The controls are the same ones Manage Data uses, laid out the same way
// (DataFilters.js:469-495): a Space of plain bordered antd widgets, a
// RangePicker with From/To placeholders and antd's calendar suffix, then
// the administration dropdown bare. The mockup drew each control inside a
// bordered pill with a borderless picker inside it, which put two idioms
// in one app and nested a bordered select in a bordered pill. The bar
// itself — the white strip — is page chrome and stays.
//
// The mockup's "Filters" pill is the per-question filter panel
// (VIZ-027): the questions come from `default_filters.questions` in the
// published snapshot, so it works on public dashboards too. See
// QuestionFilters for how ticks become filters.
//
// The export leaves the bar out (`data-html2canvas-ignore`): controls
// mean nothing on paper. ExportFilterSummary says what is filtered in
// its place, and only when something is.

const DashboardViewFilters = ({
  defaultFilters,
  rootAdministrationId = null,
  value,
  onChange,
  disabled = false,
}) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];
  // Only the summary needs it: the requests send the id.
  const [administrationName, setAdministrationName] = useState(null);

  const dateEnabled = Boolean(defaultFilters?.date?.enabled);
  const administrationEnabled = Boolean(
    defaultFilters?.administration?.enabled
  );

  const questions = Array.isArray(defaultFilters?.questions)
    ? defaultFilters.questions
    : [];

  // Nothing to offer means no bar at all, rather than an empty white strip.
  if (!dateEnabled && !administrationEnabled && !questions.length) {
    return null;
  }

  const handleDateChange = (_, dateStrings) => {
    const [from, to] = dateStrings || [];
    onChange({
      ...value,
      from_date: from || null,
      to_date: to || null,
      // Bounds the window on an answer date when the author chose one;
      // otherwise the backend bounds on FormData.created. Either way it
      // never reorders anything — "latest" stays latest by submission
      // date (VIZ-001 D-8). Resist making this sort.
      date_question_id: defaultFilters?.date?.date_question || null,
    });
  };

  const handleAdministrationChange = (level) => {
    setAdministrationName(level?.name || null);
    onChange({ ...value, administration_id: level?.id || null });
  };

  return (
    <>
      <div className="dashboard-view-filters" data-html2canvas-ignore>
        <div className="dashboard-view-filters-inner">
          {(dateEnabled || administrationEnabled) && (
            <Space className="dashboard-view-filters-card" wrap>
              {dateEnabled && (
                <RangePicker
                  disabled={disabled}
                  onChange={handleDateChange}
                  allowEmpty={[true, true]}
                  allowClear
                  placeholder={[
                    text.dateFromPlaceholder,
                    text.dateToPlaceholder,
                  ]}
                  suffixIcon={<CalendarOutlined />}
                  aria-label={text.dashboardFilterPeriod}
                />
              )}
              {administrationEnabled && (
                <AdministrationDropdownLocal
                  rootId={rootAdministrationId}
                  onChange={handleAdministrationChange}
                  loading={disabled}
                />
              )}
            </Space>
          )}
          {/* The mockup's "Filters" pill, at the right end of the bar. */}
          {questions.length > 0 && (
            <div className="dashboard-view-filters-end">
              <QuestionFilters
                questions={questions}
                value={value}
                onChange={onChange}
                disabled={disabled}
                text={text}
              />
            </div>
          )}
        </div>
        {/* The applied question filters, in a section of their own. */}
        {questions.length > 0 && (
          <ActiveFilterChips
            questions={questions}
            value={value}
            onChange={onChange}
            disabled={disabled}
            text={text}
          />
        )}
      </div>
      <ExportFilterSummary
        questions={questions}
        value={value}
        administrationName={administrationName}
        text={text}
      />
    </>
  );
};

DashboardViewFilters.propTypes = {
  defaultFilters: PropTypes.object,
  rootAdministrationId: PropTypes.oneOfType([
    PropTypes.number,
    PropTypes.string,
  ]),
  value: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  // The builder canvas shows the bar so the author can see what viewers
  // will get, but the canvas is unfiltered by design — the controls are
  // rendered inert rather than redrawn as look-alikes, which is what let
  // the two surfaces drift apart in the first place.
  disabled: PropTypes.bool,
};

export default DashboardViewFilters;
