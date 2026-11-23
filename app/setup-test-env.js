/* eslint-disable no-undef */
// Without a SafeAreaProvider in the tree useSafeAreaInsets throws; the library ships this
// mock for exactly that. Registered globally since several screens and fields read insets.
// The library's mock is an `export default {...}`, so the interop default is the module body.
// eslint-disable-next-line global-require
jest.mock(
  'react-native-safe-area-context',
  () => require('react-native-safe-area-context/jest/mock').default,
);

jest.mock('@sentry/react-native', () => ({
  init: () => jest.fn(),
  wrap: (node) => jest.fn(node),
  ReactNativeTracing: () => jest.fn(),
  ReactNavigationInstrumentation: (node) => jest.fn(node),
  reactNavigationIntegration: () => jest.fn(),
  captureMessage: (msg) => jest.fn(msg),
  captureException: (e) => jest.fn(e),
}));

jest.mock('expo-image-manipulator', () => ({
  manipulateAsync: jest.fn(),
  SaveFormat: {
    JPEG: 'jpeg',
    PNG: 'png',
    WEBP: 'webp',
  },
}));

jest.mock('expo-file-system', () => ({
  getInfoAsync: jest.fn(),
}));

jest.mock('expo-crypto', () => ({
  randomUUID: jest.fn(() => 'mock-crypto-uuid'),
}));

jest.mock('expo-task-manager', () => ({
  defineTask: jest.fn(),
  isTaskRegisteredAsync: jest.fn().mockResolvedValue(false),
  registerTaskAsync: jest.fn().mockResolvedValue(undefined),
  unregisterTaskAsync: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('expo-background-task', () => ({
  registerTaskAsync: jest.fn().mockResolvedValue(undefined),
  unregisterTaskAsync: jest.fn().mockResolvedValue(undefined),
  getStatusAsync: jest.fn().mockResolvedValue(1),
  BackgroundTaskStatus: {
    Restricted: 1,
    Denied: 2,
    Available: 3,
  },
}));

// Mock PermissionsAndroid for React Native 0.79
// eslint-disable-next-line global-require
const { PermissionsAndroid } = require('react-native');
if (PermissionsAndroid) {
  PermissionsAndroid.check = jest.fn().mockResolvedValue(true);
  PermissionsAndroid.request = jest.fn().mockResolvedValue('granted');
  PermissionsAndroid.PERMISSIONS = {
    READ_EXTERNAL_STORAGE: 'android.permission.READ_EXTERNAL_STORAGE',
    CAMERA: 'android.permission.CAMERA',
    WRITE_EXTERNAL_STORAGE: 'android.permission.WRITE_EXTERNAL_STORAGE',
    ACCESS_FINE_LOCATION: 'android.permission.ACCESS_FINE_LOCATION',
    ACCESS_COARSE_LOCATION: 'android.permission.ACCESS_COARSE_LOCATION',
  };
  PermissionsAndroid.RESULTS = {
    GRANTED: 'granted',
    DENIED: 'denied',
    NEVER_ASK_AGAIN: 'never_ask_again',
  };
}
