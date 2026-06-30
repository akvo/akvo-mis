import React, { useEffect, useCallback, useMemo } from "react";
import "./style.scss";
import { Select } from "antd";
import PropTypes from "prop-types";

import { store } from "../../lib";

const FormDropdown = ({
  loading: parentLoading = false,
  title = false,
  hidden = false,
  width = 160,
  ...props
}) => {
  const { forms, allForms, selectedForm, loadingForm } = store.useState(
    (state) => state
  );
  const filterForms = useMemo(() => {
    const form_items = title ? allForms : forms;
    return form_items.filter((f) => !f.content?.parent);
  }, [title, forms, allForms]);

  const handleChange = useCallback(
    (e) => {
      if (!e) {
        return;
      }
      store.update((s) => {
        s.loadingForm = true;
      });
      store.update((s) => {
        s.questionGroups = allForms.find(
          (f) => f.id === e
        ).content.question_group;
        s.selectedForm = e;
        s.loadingForm = false;
        s.advancedFilters = [];
        s.showAdvancedFilters = false;
      });
    },
    [allForms]
  );
  useEffect(() => {
    const findForm = allForms.find((f) => f.id === selectedForm);
    const urlParams = new URLSearchParams(window.location.search);
    if (
      urlParams.has("form_id") &&
      (urlParams.get("form_id") !== selectedForm ||
        findForm?.content?.parent !== selectedForm)
    ) {
      // If the form_id is already in the URL and the selected form is different, remove it
      urlParams.delete("form_id");
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}?${urlParams.toString()}`
      );
    }
    if (
      filterForms?.length &&
      (!selectedForm || !filterForms.map((f) => f.id).includes(selectedForm))
    ) {
      handleChange(filterForms[0].id);
    }
  }, [filterForms, selectedForm, handleChange, allForms]);
  if (filterForms && !hidden) {
    return (
      <Select
        placeholder={`Select Form`}
        style={{ width: title ? "100%" : width }}
        onChange={(e) => {
          handleChange(e);
        }}
        value={filterForms.length ? selectedForm : null}
        className={`form-dropdown ${title ? " form-dropdown-title" : ""}`}
        disabled={parentLoading || loadingForm}
        getPopupContainer={(trigger) => trigger.parentNode}
        {...props}
      >
        {filterForms.map((optionValue, optionIdx) => (
          <Select.Option key={optionIdx} value={optionValue.id}>
            {optionValue.name}
          </Select.Option>
        ))}
      </Select>
    );
  }

  return "";
};

FormDropdown.propTypes = {
  loading: PropTypes.bool,
  title: PropTypes.bool,
  hidden: PropTypes.bool,
};

export default React.memo(FormDropdown);
