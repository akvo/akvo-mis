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
  // Monotonic counter — bump to request an immediate onSync(). Counter not boolean
  // so repeated bumps always register without a reset inside the subscribe listener
  // (reentrant Pullstate updates there get swallowed).
  instantSync: 0,
  bannerVisible: false,
});

export default UIState;
