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
