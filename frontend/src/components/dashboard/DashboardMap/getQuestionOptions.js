import { getForms } from "../../../util/form";

/**
 * Look up a question's option[] by scanning the published forms (fetched at
 * app startup into the store) for the matching form_id, then walking its
 * question groups. Returns an empty array if the form, question, or its
 * options aren't found. Mirrors the helper inlined in
 * `DashboardFilters.jsx`; kept module-local to avoid scope-creeping
 * an extraction across the dashboard tree in this PR.
 */
const getQuestionOptions = (formId, questionId) => {
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

export default getQuestionOptions;
