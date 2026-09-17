/* eslint-disable import/no-unresolved */
import React from 'react';
import { act, render, waitFor, fireEvent } from '@testing-library/react-native';
// eslint-disable-next-line import/extensions
import mockBackHandler from 'react-native/Libraries/Utilities/__mocks__/BackHandler.js';

import MapDrawView from '../MapDrawView';
import { FormState, UserState } from '../../store';

const loadHtml = require('map.html');

const htmlData = `${loadHtml}`;

jest.mock('@react-navigation/native');

// @rneui Icon pulls vector-icon fonts through expo-font, which has no native binary here.
jest.mock('expo-font');

jest.mock('expo-asset', () => ({
  Asset: {
    loadAsync: jest.fn(() => Promise.resolve([{ localUri: 'mocked-uri' }])),
  },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(() => Promise.resolve(htmlData)),
}));

// RN's index reads `require('./Libraries/Utilities/BackHandler').default`, so the mock factory
// has to supply the default export rather than the module object.
jest.mock('react-native/Libraries/Utilities/BackHandler', () => ({
  __esModule: true,
  default: mockBackHandler,
}));

const mockGoBack = jest.fn();
const mockNavigate = jest.fn();

const renderScreen = (value = [], params = {}) =>
  render(
    <MapDrawView
      navigation={{ goBack: mockGoBack, navigate: mockNavigate, canGoBack: () => true }}
      route={{ params: { id: 42, value, ...params } }}
    />,
  );

const postedCommands = (webViewEl) =>
  webViewEl.props.postMessage.mock.calls.map(([payload]) => JSON.parse(payload));

// setMyLocation is an ambient heartbeat driven by Home.js's GPS watch; tests about what the
// enumerator did should not have to care how many fixes arrived meanwhile.
const captureCommands = (webViewEl) =>
  postedCommands(webViewEl).filter((c) => c.type !== 'setMyLocation');

const postFromPage = (webViewEl, points) =>
  fireEvent(webViewEl, 'onMessage', {
    nativeEvent: { data: JSON.stringify({ type: 'polygonChanged', data: { points } }) },
  });

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe('MapDrawView', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.currentValues = {};
      });
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.03, longitude: 38.74 } };
      });
    });
  });

  it('renders the webview once the html asset has loaded', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());
  });

  it('starts with the point count from the incoming value', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('text-point-count').props.children).toContain(3));
  });

  it('updates the count from a polygonChanged message', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle);
    });

    await waitFor(() => expect(getByTestId('text-point-count').props.children).toContain(3));
  });

  it('shows the area only once there are three points', async () => {
    const { getByTestId, queryByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle.slice(0, 2));
    });
    await waitFor(() => expect(queryByTestId('text-area')).toBeNull());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle);
    });
    await waitFor(() => expect(queryByTestId('text-area')).not.toBeNull());
  });

  it('ignores a malformed bridge payload instead of crashing', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      fireEvent(getByTestId('webview-map-draw'), 'onMessage', {
        nativeEvent: { data: 'not json' },
      });
    });

    expect(getByTestId('text-point-count').props.children).toContain(3);
  });

  it('writes the captured points to FormState on save and goes back', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle);
    });
    await waitFor(() => expect(getByTestId('text-point-count').props.children).toContain(3));

    act(() => {
      fireEvent.press(getByTestId('button-save-polygon'));
    });

    expect(FormState.getRawState().currentValues[42]).toEqual(triangle);
    expect(mockGoBack).toHaveBeenCalled();
  });

  it('stores latitude first, matching the web format', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle);
    });
    await waitFor(() => expect(getByTestId('text-point-count').props.children).toContain(3));

    act(() => {
      fireEvent.press(getByTestId('button-save-polygon'));
    });

    const [[lat, lng]] = FormState.getRawState().currentValues[42];
    expect(lat).toBe(9.03);
    expect(lng).toBe(38.74);
  });
});

describe('MapDrawView input method dialog', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.currentValues = {};
      });
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.03, longitude: 38.74, accuracy: 18.4 } };
      });
    });
  });

  it('stays closed until the add-point button is pressed', () => {
    const { queryByTestId, getByTestId } = renderScreen();
    expect(queryByTestId('button-start-input-method')).toBeNull();

    fireEvent.press(getByTestId('button-add-point'));

    expect(getByTestId('button-start-input-method')).toBeDefined();
  });

  it('offers all three ODK capture modes', () => {
    const { getByTestId } = renderScreen();
    fireEvent.press(getByTestId('button-add-point'));
    expect(getByTestId('option-input-method-tapping')).toBeDefined();
    expect(getByTestId('option-input-method-manual')).toBeDefined();
    expect(getByTestId('option-input-method-automatic')).toBeDefined();
  });

  it('enables only tapping - both recording modes land with GEO-004', () => {
    const { getByTestId } = renderScreen();
    fireEvent.press(getByTestId('button-add-point'));
    expect(getByTestId('option-input-method-tapping').props.accessibilityState.disabled).toBe(
      false,
    );
    expect(getByTestId('option-input-method-manual').props.accessibilityState.disabled).toBe(true);
    expect(getByTestId('option-input-method-automatic').props.accessibilityState.disabled).toBe(
      true,
    );
  });

  it('dismisses without leaving the screen or adding a point', async () => {
    const { getByTestId, queryByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-add-point'));
    fireEvent.press(getByTestId('button-cancel-input-method'));

    expect(mockGoBack).not.toHaveBeenCalled();
    expect(queryByTestId('button-start-input-method')).toBeNull();
    expect(captureCommands(getByTestId('webview-map-draw'))).toEqual([]);
  });

  it('shows the live GPS accuracy', () => {
    const { getByTestId } = renderScreen();
    expect(getByTestId('text-accuracy').props.children).toContain('18 m');
  });
});

describe('MapDrawView controls', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.currentValues = {};
      });
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.03, longitude: 38.74, accuracy: 18.4 } };
      });
    });
  });

  it('arms map tapping only once the mode is started', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-add-point'));
    // The pin opens the chooser; the page is not armed and nothing is placed.
    expect(captureCommands(getByTestId('webview-map-draw'))).toEqual([]);

    fireEvent.press(getByTestId('button-start-input-method'));

    expect(postedCommands(getByTestId('webview-map-draw'))).toContainEqual({
      type: 'setTapping',
      data: { enabled: true },
    });
  });

  it('does not arm tapping when the chooser is cancelled', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-add-point'));
    fireEvent.press(getByTestId('button-cancel-input-method'));

    expect(captureCommands(getByTestId('webview-map-draw'))).toEqual([]);
  });

  it('drops a point at the map centre once tapping is running, ODK style', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-add-point'));
    fireEvent.press(getByTestId('button-start-input-method'));
    // Second press: the mode is running, so the pin no longer reopens the chooser.
    fireEvent.press(getByTestId('button-add-point'));

    expect(postedCommands(getByTestId('webview-map-draw'))).toContainEqual({
      type: 'addAtCenter',
      data: {},
    });
  });

  it('undoes by sending the shortened array, not a delta', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-undo'));

    expect(postedCommands(getByTestId('webview-map-draw'))).toContainEqual({
      type: 'setPoints',
      data: { points: triangle.slice(0, -1) },
    });
  });

  it('clears without confirming at or below three points', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-clear'));

    expect(postedCommands(getByTestId('webview-map-draw'))).toContainEqual({
      type: 'setPoints',
      data: { points: [] },
    });
  });

  it('recentres without appending a point', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-centre-on-me'));

    const commands = captureCommands(getByTestId('webview-map-draw'));
    expect(commands).toContainEqual({ type: 'centreOnMe', data: { lat: 9.03, lng: 38.74 } });
    expect(commands.some((c) => c.type === 'addAtCenter')).toBe(false);
  });

  it('pushes the live fix to the page without rebuilding it', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());
    const firstHtml = getByTestId('webview-map-draw').props.source.html;

    act(() => {
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.04, longitude: 38.75, accuracy: 12 } };
      });
    });

    await waitFor(() =>
      expect(postedCommands(getByTestId('webview-map-draw'))).toContainEqual({
        type: 'setMyLocation',
        data: { lat: 9.04, lng: 38.75, accuracy: 12 },
      }),
    );
    /**
     * Home.js pushes a fix every few seconds. If the page were keyed on it the WebView would
     * be rebuilt each time and the captured polygon lost, so the source must be untouched.
     */
    expect(getByTestId('webview-map-draw').props.source.html).toBe(firstHtml);
  });

  it('disables undo and clear with nothing captured', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());
    expect(getByTestId('button-undo').props.accessibilityState.disabled).toBe(true);
    expect(getByTestId('button-clear').props.accessibilityState.disabled).toBe(true);
  });
});

describe('MapDrawView hardware back', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.currentValues = {};
      });
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.03, longitude: 38.74, accuracy: 18.4 } };
      });
    });
  });

  /**
   * FormPage keeps its own hardwareBackPress listener registered while this screen is on top,
   * so if this screen does not claim the press the form underneath handles it.
   */
  it('returns to the form instead of letting the press fall through', async () => {
    const { getByTestId, unmount } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(mockGoBack).toHaveBeenCalled();
    expect(mockBackHandler.exitApp).not.toHaveBeenCalled();
    unmount();
  });

  /**
   * React Navigation 6 REPLACES params on navigate unless merge is set, so navigating to
   * FormPage by name with no params blanked its id/name/newSubmission. FormPage then submitted
   * as an UPDATE of a row with no id: a silent no-op that still toasted success and lost the
   * submission. Popping leaves the route below untouched.
   */
  it('pops rather than navigating by name, which would blank FormPage params', async () => {
    const { getByTestId, unmount } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(mockNavigate).not.toHaveBeenCalledWith('FormPage');
    expect(mockNavigate).not.toHaveBeenCalled();
    unmount();
  });

  it('discards rather than saving - only the save control commits', async () => {
    const { getByTestId, unmount } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    act(() => {
      postFromPage(getByTestId('webview-map-draw'), triangle);
    });
    await waitFor(() => expect(getByTestId('text-point-count').props.children).toContain(3));

    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(FormState.getRawState().currentValues[42]).toBeUndefined();
    unmount();
  });

  it('closes the input method dialog first', async () => {
    const { getByTestId, queryByTestId, unmount } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());

    fireEvent.press(getByTestId('button-add-point'));

    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(queryByTestId('button-start-input-method')).toBeNull();
    expect(mockGoBack).not.toHaveBeenCalled();
    unmount();
  });

  it('removes its listener on unmount', async () => {
    const { getByTestId, unmount } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());
    unmount();

    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(mockGoBack).not.toHaveBeenCalled();
  });
});

describe('MapDrawView geotrace', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
        s.currentValues = {};
      });
      UserState.update((s) => {
        s.currentLocation = { coords: { latitude: 9.03, longitude: 38.74, accuracy: 18.4 } };
      });
    });
  });

  it('reports no area for an open line', async () => {
    const { getByTestId, queryByTestId } = renderScreen(triangle, { type: 'geotrace' });
    await waitFor(() => expect(getByTestId('webview-map-draw')).toBeDefined());
    expect(getByTestId('text-point-count').props.children).toContain(3);
    expect(queryByTestId('text-area')).toBeNull();
  });

  it('still reports area for a geoshape', async () => {
    const { getByTestId } = renderScreen(triangle, { type: 'geoshape' });
    await waitFor(() => expect(getByTestId('text-area')).toBeDefined());
  });

  it('defaults to a closed shape when the type is absent', async () => {
    const { getByTestId } = renderScreen(triangle);
    await waitFor(() => expect(getByTestId('text-area')).toBeDefined());
  });
});
