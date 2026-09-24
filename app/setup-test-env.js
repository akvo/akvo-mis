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
