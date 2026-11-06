import { Store } from 'pullstate';

const DatapointSyncState = new Store({
  inProgress: false,
  progress: 0,
  added: false,
  completed: false,
  syncingFormId: null,
  formProgress: {},
});

export default DatapointSyncState;
