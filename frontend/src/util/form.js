import { store, api } from "../lib";

export const sortArray = (x, y) => {
  const nameOne = x.name.toLowerCase();
  const nameTwo = y.name.toLowerCase();
  if (nameOne < nameTwo) {
    return -1;
  }
  if (nameOne > nameTwo) {
    return 1;
  }
  return 0;
};

// Snapshot accessor for non-component code (helpers, lookups) that used to
// read the window.forms global. Components should prefer
// store.useState((s) => s.allForms) so they re-render on updates.
export const getForms = () => store.getRawState().allForms || [];

const filterFormByAssigment = (profile = {}, allForms = []) => {
  if (!Object.keys(profile).length) {
    return allForms;
  }
  return profile.forms.length
    ? allForms.filter((x) => profile.forms.map((f) => f.id).includes(x.id))
    : allForms;
};

export const reloadData = (profile = {}, dataset = []) => {
  const allForms = getForms();
  const filterForms = filterFormByAssigment(profile, allForms);
  const updatedForms = dataset.length
    ? filterForms.map((x) => {
        const newForm = dataset.find((d) => d.id === x.id);
        if (newForm) {
          return { ...x, ...newForm };
        }
        return x;
      })
    : filterForms;
  store.update((s) => {
    s.forms = updatedForms;
  });
};

// Fetch the published forms (with full content) once at app bootstrap and
// populate the store. Replaces the window.forms global baked into config.js.
export const fetchPublishedForms = () =>
  api.get("forms/published").then((res) => {
    const data = Array.isArray(res?.data) ? res.data : [];
    const allForms = data.slice().sort(sortArray);
    store.update((s) => {
      s.allForms = allForms;
    });
    // Recompute the assignment-filtered list now that allForms is available,
    // covering the case where the profile fetch resolved before this one.
    const { user } = store.getRawState();
    reloadData(user || {});
    return allForms;
  });
