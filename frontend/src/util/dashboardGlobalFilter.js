// VIZ-027 (D-15, D-20, D-21): {"<form>:<name>": [ticked values]} -> one
// "option_in:<form>:<name>:<value>" per value, or null. Sorted, so equal
// selections give equal lists and widgets keep sharing cache keys. null
// lets compact() drop the parameter, so an unfiltered dashboard sends
// exactly what it sends today.
export const serializeGlobalCriteria = (selections) => {
  const entries = Object.entries(selections || {})
    .filter(([, values]) => values?.length)
    .sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }))
    .flatMap(([key, values]) =>
      [...values].sort().map((v) => `option_in:${key}:${v}`)
    );
  return entries.length ? entries : null;
};

// The backend refuses more values than this in one request (D-15,
// MAX_GLOBAL_CRITERIA in backend/api/v1/v1_visualization/constants.py).
export const MAX_GLOBAL_CRITERIA = 50;

// The key a filter question is selected under: its form and name (D-20).
export const filterKey = (form, name) => `${form}:${name}`;
