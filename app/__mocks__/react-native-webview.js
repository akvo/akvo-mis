/**
 * react-native-webview reaches for the RNCWebViewModule turbo module at import time, which
 * does not exist under Jest. Mocked at the package level so every WebView-hosting screen can
 * be tested; ref.postMessage is a spy so the RN -> page commands can be asserted, and props
 * are forwarded so tests can assert on source, scrollEnabled and the rest.
 */
const React = require('react');
const { View } = require('react-native');

const WebView = React.forwardRef((props, ref) => {
  const postMessage = React.useRef(jest.fn()).current;
  React.useImperativeHandle(ref, () => ({ postMessage }), [postMessage]);
  return React.createElement(View, { ...props, postMessage });
});

WebView.displayName = 'WebView';

module.exports = { WebView, default: WebView };
