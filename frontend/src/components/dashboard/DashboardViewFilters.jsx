import React from "react";
import PropTypes from "prop-types";
import { DatePicker, Space } from "antd";
import { CalendarOutlined } from "@ant-design/icons";
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
// The controls are the same ones Manage Data uses, laid out the same way
// (DataFilters.js:469-495): a Space of plain bordered antd widgets, a
// RangePicker with From/To placeholders and antd's calendar suffix, then
// the administration dropdown bare. The mockup drew each control inside a
// bordered pill with a borderless picker inside it, which put two idioms
// in one app and nested a bordered select in a bordered pill. The bar
// itself — the white strip — is page chrome and stays.
//
// Not built: the mockup's blue "Filters" pill. Custom per-question filters
// are not part of the `default_filters` schema (VIZ-001 §4.4), and adding
// them would mean inventing a persistence format this slice cannot save.

const DashboardViewFilters = ({
  defaultFilters,
  value,
  onChange,
  disabled = false,
}) => {
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
        <Space>
          {dateEnabled && (
            <RangePicker
              disabled={disabled}
              onChange={handleDateChange}
              allowEmpty={[true, true]}
              allowClear
              placeholder={[text.dateFromPlaceholder, text.dateToPlaceholder]}
              suffixIcon={<CalendarOutlined />}
              aria-label={text.dashboardFilterPeriod}
            />
          )}
          {administrationEnabled && (
            <AdministrationDropdownLocal
              onChange={handleAdministrationChange}
              loading={disabled}
            />
          )}
        </Space>
      </div>
    </div>
  );
};

DashboardViewFilters.propTypes = {
  defaultFilters: PropTypes.object,
  value: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  // The builder canvas shows the bar so the author can see what viewers
  // will get, but the canvas is unfiltered by design — the controls are
  // rendered inert rather than redrawn as look-alikes, which is what let
  // the two surfaces drift apart in the first place.
  disabled: PropTypes.bool,
};

export default DashboardViewFilters;
