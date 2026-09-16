import React from 'react';
import { act, render, fireEvent } from '@testing-library/react-native';
import { useNavigation } from '@react-navigation/native';

import TypeGeoDrawing from '../TypeGeoDrawing';
import { FormState } from '../../../store';

jest.mock('@react-navigation/native');

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe('TypeGeoDrawing', () => {
  beforeEach(() => {
    act(() => {
      FormState.update((s) => {
        s.lang = 'en';
      });
    });
  });

  it('prompts when nothing has been captured', () => {
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" />,
    );
    expect(getByTestId('text-no-points')).toBeDefined();
    expect(queryByTestId('text-point-count')).toBeNull();
    expect(queryByTestId('text-area')).toBeNull();
  });

  it('shows the point count and area for a captured shape', () => {
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );
    expect(getByTestId('text-point-count').props.children).toContain(3);
    expect(getByTestId('text-area')).toBeDefined();
  });

  it('withholds the area below three points', () => {
    const { queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle.slice(0, 2)} />,
    );
    expect(queryByTestId('text-point-count').props.children).toContain(2);
    expect(queryByTestId('text-area')).toBeNull();
  });

  it('tolerates a non-array value instead of crashing', () => {
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value="" />,
    );
    expect(getByTestId('text-no-points')).toBeDefined();
  });

  it('opens the map screen with the current points', () => {
    const navigation = useNavigation();
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );

    fireEvent.press(getByTestId('button-draw-on-map'));

    expect(navigation.navigate).toHaveBeenCalledWith('MapDrawView', {
      id: 42,
      value: triangle,
      name: 'Plot boundary',
      type: 'geoshape',
    });
  });

  it('does not render a map of its own', () => {
    const { queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Plot boundary" value={triangle} />,
    );
    expect(queryByTestId('webview-map-draw')).toBeNull();
  });

  it('passes the question type through to the map screen', () => {
    const navigation = useNavigation();
    const { getByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Route walked" type="geotrace" value={triangle} />,
    );

    fireEvent.press(getByTestId('button-draw-on-map'));

    expect(navigation.navigate).toHaveBeenCalledWith('MapDrawView', {
      id: 42,
      value: triangle,
      name: 'Route walked',
      type: 'geotrace',
    });
  });

  /**
   * A geotrace is an open line: it encloses nothing, so reporting an area for it would be
   * a number with no meaning.
   */
  it('reports no area for a geotrace', () => {
    const { getByTestId, queryByTestId } = render(
      <TypeGeoDrawing keyform={0} id={42} label="Route walked" type="geotrace" value={triangle} />,
    );
    expect(getByTestId('text-point-count').props.children).toContain(3);
    expect(queryByTestId('text-area')).toBeNull();
  });
});
