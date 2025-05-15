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
  currentGroup: null, // to store the currently active question group
  forceUpdateToken: null, // to force re-render when needed
});

export default FormState;
