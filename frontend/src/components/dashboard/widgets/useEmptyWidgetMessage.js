import { store, uiText } from "../../../lib";

export const hasActiveDashboardFilters = (filters) =>
  Boolean(
    filters &&
      (filters.from_date || filters.to_date || filters.administration_id)
  );

export const getEmptyWidgetMessage = (filters, text) => {
  if (hasActiveDashboardFilters(filters)) {
    return (
      text?.dashboardWidgetNoDataFiltered || "No data found for current filters"
    );
  }
  return text?.dashboardWidgetNoData || "No data available";
};

const useEmptyWidgetMessage = (filters) => {
  const { language } = store.useState((s) => s);
  const text = uiText[language?.active] || uiText.en;
  return getEmptyWidgetMessage(filters, text);
};

export default useEmptyWidgetMessage;
