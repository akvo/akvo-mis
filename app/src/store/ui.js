import { Store } from 'pullstate';

const UIState = new Store({
  isDarkMode: false, // if isDarkMode = false then Theme= light
  darkModePreference: 'auto', // 'auto' | 'light' | 'dark'
  lang: 'en',
  fontSize: 16,
  currentPage: 'GetStarted',
  online: false,
  networkType: null,
  isManualSynced: false,
  statusBar: null,
  refreshPage: false,
  lowStorage: false,
  triggerSync: false,
});

export default UIState;
