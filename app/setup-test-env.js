/* eslint-disable no-undef */
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
