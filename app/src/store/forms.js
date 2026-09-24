import { Store } from 'pullstate';

const FormState = new Store({
  form: {},
  currentValues: {}, // answers
  visitedQuestionGroup: [], // to store visited question group id
  surveyDuration: 0,
  surveyStart: null,
  cascades: {},
  lang: 'en',
  feedback: {},
  /**
   * Stored polygon validation, keyed by question id: `{ status, results, retryable, at }`.
   *
   * Overlap detection is user-initiated and expensive, so the submit gate reads what the
   * Validate button last produced instead of re-running the geometry (GEO-007 D-1). Editing the
   * polygon clears its entry, which is what returns the field to "not validated".
   */
  polygonValidation: {},
  /**
   * The submission being filled, and the form whose datapoints are overlap candidates.
   *
   * Published by FormPage because the geoshape field needs both and sits several levels below
   * it: the uuid excludes the datapoint from its own overlap check (without it every edit
   * overlaps itself by 100 %), and the form id scopes the candidate query.
   */
  submissionUuid: null,
  overlapFormId: null,
  loading: false,
  prevAdmAnswer: null,
  entityOptions: {},
  repeats: {}, // to store repeatable question groups: { groupId: [0, 1, 2, ...] }
  forceUpdateToken: null, // to force re-render when needed
  previousForm: null,
  // True once anything has written to currentValues that was not the app itself
  // loading or clearing them. Gates the save/exit dialog: without it, opening a saved
  // draft and pressing back always prompted, because loading the answers looked the
  // same as entering them.
  hasUnsavedChanges: false,
});

export default FormState;
