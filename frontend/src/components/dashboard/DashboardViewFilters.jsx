import React from "react";
import PropTypes from "prop-types";
import { DatePicker } from "antd";
import AdministrationDropdownLocal from "../filters/AdministrationDropdownLocal";
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
// Not built: the mockup's blue "Filters" pill. Custom per-question filters
// are not part of the `default_filters` schema (VIZ-001 §4.4), and adding
// them would mean inventing a persistence format this slice cannot save.

const CalendarIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <rect
      x="3"
      y="4"
      width="18"
      height="17"
      rx="2"
      stroke="#5b6472"
      strokeWidth="1.6"
    />
    <path d="M3 9h18M8 2v4M16 2v4" stroke="#5b6472" strokeWidth="1.6" />
  </svg>
);

const DashboardViewFilters = ({ defaultFilters, value, onChange }) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language.active];

  const dateEnabled = Boolean(defaultFilters?.date?.enabled);
  const administrationEnabled = Boolean(
    defaultFilters?.administration?.enabled
  );

  // Neither enabled means no bar at all, rather than an empty white strip.
  if (!dateEnabled && !administrationEnabled) {
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
    onChange({ ...value, administration_id: level?.id || null });
  };

  return (
    <div className="dashboard-view-filters">
      <div className="dashboard-view-filters-inner">
        {dateEnabled && (
          <div className="dashboard-view-chip">
            <CalendarIcon />
            <RangePicker
              onChange={handleDateChange}
              allowEmpty={[true, true]}
              bordered={false}
              suffixIcon={null}
              aria-label={text.dashboardFilterPeriod}
            />
          </div>
        )}
        {administrationEnabled && (
          <div className="dashboard-view-chip">
            <AdministrationDropdownLocal
              onChange={handleAdministrationChange}
              width={150}
            />
          </div>
        )}
      </div>
    </div>
  );
};

DashboardViewFilters.propTypes = {
  defaultFilters: PropTypes.object,
  value: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
};

export default DashboardViewFilters;
