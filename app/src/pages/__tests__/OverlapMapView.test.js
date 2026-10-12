/* eslint-disable import/no-unresolved */
import React from 'react';
import { act, render, waitFor, fireEvent } from '@testing-library/react-native';
// eslint-disable-next-line import/extensions
import mockBackHandler from 'react-native/Libraries/Utilities/__mocks__/BackHandler.js';

import OverlapMapView from '../OverlapMapView';
import { FormState, UIState } from '../../store';

const loadHtml = require('map.html');

const htmlData = `${loadHtml}`;

jest.mock('@react-navigation/native');

// @rneui Icon pulls vector-icon fonts through expo-font, which has no native binary here.
jest.mock('expo-font');

// RN's index reads `require('./Libraries/Utilities/BackHandler').default`, so the mock factory
// has to supply the default export rather than the module object.
jest.mock('react-native/Libraries/Utilities/BackHandler', () => ({
  __esModule: true,
  default: mockBackHandler,
}));

jest.mock('expo-asset', () => ({
  Asset: {
    loadAsync: jest.fn(() => Promise.resolve([{ localUri: 'mocked-uri' }])),
  },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(() => Promise.resolve(htmlData)),
}));

const mockGoBack = jest.fn();

const CURRENT = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

/**
 * Already labelled, worst first — the shape `TypeGeoDrawing` puts on the route after running the
 * conflicts through `conflictsForMap`. The screen labels nothing itself, so `#2` here and `#2` in
 * the error sentence cannot disagree.
 */
const CONFLICTS = [
  {
    label: '#1',
    name: 'Amina Kebede - Bole - Kebele 3',
    percent: '34.0',
    coordinates: [
      [9.031, 38.741, 22],
      [9.031, 38.751],
      [9.041, 38.751],
    ],
  },
  {
    label: '#2',
    name: 'Dawit Alemu - Bole - Kebele 4',
    percent: '28.3',
    coordinates: [
      [9.029, 38.739],
      [9.029, 38.749],
      [9.039, 38.749],
    ],
  },
];

const renderScreen = (params = {}) =>
  render(
    <OverlapMapView
      navigation={{ goBack: mockGoBack, canGoBack: () => true }}
      route={{
        params: {
          value: CURRENT,
          conflicts: CONFLICTS,
          name: 'Plot boundary',
          accuracyThreshold: 15,
          ...params,
        },
      }}
    />,
  );

const tapPolygon = (webViewEl, index) =>
  fireEvent(webViewEl, 'onMessage', {
    nativeEvent: { data: JSON.stringify({ type: 'polygonTapped', data: { index } }) },
  });

describe('OverlapMapView', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
      });
      UIState.update((s) => {
        s.online = true;
      });
    });
  });

  it('renders the map once the page has loaded', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-overlap-map')).toBeTruthy());
  });

  /**
   * The error sentence names positions, not people: `Overlaps 2 plots: #1 (34.0%), #2 (28.3%)`.
   * This is the only place a name appears, so tapping has to produce the right one - a panel
   * showing #1's farmer while #2 is highlighted sends the enumerator to the wrong gate.
   */
  it('names the conflicting plot that was tapped', async () => {
    const { getByTestId } = renderScreen();
    const webView = await waitFor(() => getByTestId('webview-overlap-map'));

    act(() => tapPolygon(webView, 1));

    expect(getByTestId('text-selected-name').props.children).toBe('Dawit Alemu - Bole - Kebele 4');
    expect(getByTestId('text-selected-label').props.children).toBe('#2');
  });

  it('says which plot is being worked on when that one is tapped', async () => {
    const { getByTestId } = renderScreen();
    const webView = await waitFor(() => getByTestId('webview-overlap-map'));

    act(() => tapPolygon(webView, null));

    expect(getByTestId('text-selected-name').props.children).toBe('The plot you are working on');
  });

  it('shows nothing selected until a polygon is tapped', async () => {
    const { queryByTestId } = renderScreen();
    await waitFor(() => expect(queryByTestId('webview-overlap-map')).toBeTruthy());
    expect(queryByTestId('text-selected-name')).toBeNull();
  });

  /**
   * Driven by the resolver's verdict, never by a connectivity check (D-1). Today the two agree,
   * because nothing is ever stored on the device; the day a pack is downloaded this is the line
   * that stops the screen claiming there is no imagery under a perfectly good one.
   */
  it('says imagery is unavailable when the resolver found no tiles', async () => {
    act(() => {
      UIState.update((s) => {
        s.online = false;
      });
    });
    const { getByTestId, queryByTestId } = renderScreen();

    await waitFor(() => expect(getByTestId('text-imagery-offline')).toBeTruthy());
    expect(queryByTestId('text-imagery-disclaimer')).toBeNull();
  });

  it('warns the imagery may be out of date, and only when there is imagery', async () => {
    const { getByTestId, queryByTestId } = renderScreen();

    await waitFor(() => expect(getByTestId('text-imagery-disclaimer')).toBeTruthy());
    expect(queryByTestId('text-imagery-offline')).toBeNull();
  });

  /**
   * GEO-014 §8: the red dot is a GPS-quality mark, not a verdict on anyone's boundary. A legend
   * that reads "not verified" would have the enumerator re-walking a corner because a neighbour
   * disputed it.
   */
  it('describes the red dot as GPS accuracy, never as verification', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('text-legend-accuracy')).toBeTruthy());

    const legend = getByTestId('text-legend-accuracy').props.children;
    expect(legend).toBe('GPS accuracy worse than 15 m');
    expect(legend).not.toMatch(/verif|valid|confirm|disput/i);
  });

  it('marks nothing when the question sets no accuracy threshold', async () => {
    // `accuracyThreshold: 0` is the page's "no marking", and a legend promising red dots that
    // can never appear is worse than no legend.
    const { queryByTestId, getByTestId } = renderScreen({ accuracyThreshold: 0 });
    await waitFor(() => expect(getByTestId('webview-overlap-map')).toBeTruthy());
    expect(queryByTestId('text-legend-accuracy')).toBeNull();
  });

  /**
   * D-2: one editing surface per value. A save button here would make the map a second place to
   * move a corner, and the two would have to be kept in step for no benefit.
   */
  it('offers no way to edit the polygon', async () => {
    const { queryByTestId, getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-overlap-map')).toBeTruthy());

    ['button-save-polygon', 'button-add-point', 'button-undo', 'button-clear'].forEach((testID) => {
      expect(queryByTestId(testID)).toBeNull();
    });
  });

  it('leaves through the back control without touching the form', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-overlap-map')).toBeTruthy());

    fireEvent.press(getByTestId('button-close-overlap-map'));

    expect(mockGoBack).toHaveBeenCalled();
  });

  /**
   * FormPage's hardwareBackPress listener has no focus guard, so a screen pushed on top of it
   * has to claim the event or a back press is handled by the form underneath - discarding it.
   */
  it('claims the hardware back press instead of letting the form handle it', async () => {
    const { getByTestId } = renderScreen();
    await waitFor(() => expect(getByTestId('webview-overlap-map')).toBeTruthy());

    mockGoBack.mockClear();
    act(() => {
      mockBackHandler.mockPressBack();
    });

    expect(mockGoBack).toHaveBeenCalled();
    // The mock calls exitApp only when no listener claimed the event.
    expect(mockBackHandler.exitApp).not.toHaveBeenCalled();
  });
});
