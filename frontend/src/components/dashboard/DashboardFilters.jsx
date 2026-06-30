import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, DatePicker, Popover, Select, Tag } from "antd";
import { FilterOutlined } from "@ant-design/icons";
import PropTypes from "prop-types";
import AdministrationDropdown from "../filters/AdministrationDropdown";
import { store } from "../../lib";
import { getForms } from "../../util/form";

const { RangePicker } = DatePicker;

/**
 * Look up a question's option[] by scanning the published forms (fetched at
 * app startup into the store) for the matching form_id, then walking its
 * question groups. Returns an empty array if the form, question, or its
 * options aren't found.
 */
const extractOptionsFromStore = (formId, questionId) => {
  const form = getForms().find((f) => f.id === Number(formId));
  const groups = form?.content?.question_group || [];
  for (let i = 0; i < groups.length; i += 1) {
    const q = (groups[i].question || []).find((x) => x.id === questionId);
    if (q) {
      return (q.option || []).map((o) => ({
        label: o.label,
        value: o.value,
      }));
    }
  }
  return [];
};

/**
 * Filter bar for the config-driven dashboard. Renders filters from a flat
 * array of filter items (the `items[]` contents of a `filter_bar` container).
 *
 * Recognises:
 *   - `filter_date`           → <RangePicker>
 *   - `filter_administration` → <AdministrationDropdown>
 *   - `filter_option`         → <Select> (single)
 *   - `filter_multi_option`   → <Select mode="multiple">
 *
 * Hidden items (`hide: true`) are skipped.
 *
 * The component is intentionally display-only: state and query-string
 * synthesis live in `useDashboardFilters` + `lib/dashboardFilterHints`.
 *
 * @param {Array}  filterItems   Flat list of filter items from the filter_bar container
 * @param {object} filters       Return value of useDashboardFilters
 * @param {object} onChange      { setDateRange, setAdministrationId, setCustomFilter }
 */
const DashboardFilters = ({ filterItems, filters, onChange }) => {
  const dateCfg = useMemo(
    () => filterItems.find((i) => i.chart_type === "filter_date"),
    [filterItems]
  );

  const adminCfg = useMemo(
    () => filterItems.find((i) => i.chart_type === "filter_administration"),
    [filterItems]
  );

  const customDefs = useMemo(
    () =>
      filterItems.filter(
        (i) =>
          (i.chart_type === "filter_option" ||
            i.chart_type === "filter_multi_option") &&
          !i.hide
      ),
    [filterItems]
  );

  // Resolve option lists for each custom filter from the published forms in
  // the store (fetched at app startup). No extra fetch required.
  const customOptions = useMemo(() => {
    const out = {};
    customDefs.forEach((d) => {
      out[d.key] = extractOptionsFromStore(d.form_id, d.question_id);
    });
    return out;
  }, [customDefs]);

  // AdministrationDropdown is the source of truth via `store.administration`
  // (an array of levels). It does NOT fire onChange on clear, so we subscribe
  // to the store instead and derive the deepest selected admin id ourselves.
  const adminPath = store.useState((s) => s.administration);
  const { setAdministrationId } = onChange;
  useEffect(() => {
    const deepest = (adminPath || [])
      .slice()
      .reverse()
      .find((level) => level?.id)?.id;
    setAdministrationId(deepest || null);
  }, [adminPath, setAdministrationId]);

  const handleDateChange = (_, dateStrings) => {
    const [from, to] = dateStrings || [];
    onChange.setDateRange(from || null, to || null);
  };

  const handleCustomChange = (key) => (value) => {
    onChange.setCustomFilter(key, value ?? null);
  };

  const customValue = (key) => {
    return filters?.state?.custom?.find((c) => c.key === key)?.value;
  };

  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeAdvancedCount = useMemo(
    () =>
      customDefs.reduce((acc, d) => {
        const v = customValue(d.key);
        if (v === null || typeof v === "undefined" || v === "") {
          return acc;
        }
        if (Array.isArray(v) && v.length === 0) {
          return acc;
        }
        return acc + 1;
      }, 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [customDefs, filters?.state?.custom]
  );

  const advancedContent = (
    <div className="dashboard-filter-advanced">
      <div className="advanced-title">Advanced filters</div>
      {customDefs.map((d) => (
        <div className="advanced-field" key={d.key}>
          <label>{d.label}</label>
          <Select
            allowClear
            placeholder={d.label}
            style={{ width: "100%" }}
            value={customValue(d.key) || []}
            onChange={handleCustomChange(d.key)}
            {...(d.chart_type === "filter_multi_option"
              ? { mode: "multiple" }
              : {})}
            options={customOptions[d.key] || []}
          />
        </div>
      ))}
    </div>
  );

  const dateFrom = filters?.state?.from_date;
  const dateTo = filters?.state?.to_date;
  const adminName = useMemo(() => {
    const deepest = (adminPath || [])
      .filter((a) => a.level)
      .slice()
      .reverse()
      .find((level) => level?.id);
    return deepest?.full_name?.replace(/\|/g, " - ") || deepest?.name || null;
  }, [adminPath]);

  const labelForCustomValue = (def, value) => {
    const opts = customOptions[def.key] || [];
    if (Array.isArray(value)) {
      const names = value.map(
        (v) => opts.find((o) => o.value === v)?.label || v
      );
      return names.join(", ");
    }
    return opts.find((o) => o.value === value)?.label || String(value);
  };

  const selectedTags = [];
  if (dateFrom) {
    selectedTags.push({
      key: "date-from",
      label: `from ${dateFrom}`,
      onClose: () => onChange.setDateRange(null, dateTo || null),
    });
  }
  if (dateTo) {
    selectedTags.push({
      key: "date-to",
      label: `to ${dateTo}`,
      onClose: () => onChange.setDateRange(dateFrom || null, null),
    });
  }
  if (adminName) {
    selectedTags.push({
      key: "admin",
      label: adminName,
      onClose: () => {
        store.update((s) => {
          s.administration = (s.administration || []).map((level, idx) =>
            idx === 0 ? level : { ...level, id: null, name: null }
          );
        });
      },
    });
  }
  customDefs.forEach((d) => {
    const v = customValue(d.key);
    const hasValue =
      v !== null &&
      typeof v !== "undefined" &&
      v !== "" &&
      !(Array.isArray(v) && v.length === 0);
    if (hasValue) {
      selectedTags.push({
        key: `custom-${d.key}`,
        label: `${d.label}: ${labelForCustomValue(d, v)}`,
        onClose: () => onChange.setCustomFilter(d.key, null),
      });
    }
  });

  return (
    <div className="dashboard-filters-wrapper">
      <div className="dashboard-filters">
        <div className="filter-group filter-group-fixed">
          {dateCfg && !dateCfg.hide && (
            <RangePicker
              onChange={handleDateChange}
              allowEmpty={[true, true]}
              aria-label={dateCfg.label || "Date range"}
            />
          )}
          {adminCfg && !adminCfg.hide && <AdministrationDropdown />}
        </div>
        {customDefs.length > 0 && (
          <div className="filter-group filter-group-dynamic">
            <Popover
              trigger="click"
              placement="bottomRight"
              open={advancedOpen}
              onOpenChange={setAdvancedOpen}
              content={advancedContent}
              overlayClassName="dashboard-filter-popover"
            >
              <Badge count={activeAdvancedCount} offset={[-4, 4]}>
                <Button
                  type={activeAdvancedCount > 0 ? "primary" : "default"}
                  shape="round"
                  icon={<FilterOutlined />}
                >
                  Filters
                </Button>
              </Badge>
            </Popover>
          </div>
        )}
      </div>
      {selectedTags.length > 0 && (
        <div className="dashboard-selected-filters">
          <span className="selected-filters-label">Selected filters:</span>
          {selectedTags.map((t) => (
            <Tag key={t.key} closable onClose={t.onClose} color="blue">
              {t.label}
            </Tag>
          ))}
        </div>
      )}
    </div>
  );
};

DashboardFilters.propTypes = {
  filterItems: PropTypes.arrayOf(PropTypes.object).isRequired,
  filters: PropTypes.object.isRequired,
  onChange: PropTypes.shape({
    setDateRange: PropTypes.func.isRequired,
    setAdministrationId: PropTypes.func.isRequired,
    setCustomFilter: PropTypes.func.isRequired,
  }).isRequired,
};

export default DashboardFilters;
