/* eslint-disable import/no-unresolved */
import React from 'react';
import { render, waitFor } from '@testing-library/react-native';

import GeoshapeView from '../GeoshapeView';

const loadHtml = require('map.html');

const htmlData = `${loadHtml}`;

jest.mock('expo-asset', () => ({
  Asset: {
    loadAsync: jest.fn(() => Promise.resolve([{ localUri: 'mocked-uri' }])),
  },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(() => Promise.resolve(htmlData)),
}));

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

describe('GeoshapeView', () => {
  it('renders a dash when there is no shape', () => {
    const { getByTestId, queryByTestId } = render(<GeoshapeView index={0} answer={null} />);
    expect(getByTestId('text-answer-0').props.children).toBe('-');
    expect(queryByTestId('webview-geoshape-0')).toBeNull();
  });

  it('renders a dash for an empty array', () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer={[]} />);
    expect(getByTestId('text-answer-0').props.children).toBe('-');
  });

  it('previews the shape on a map', async () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer={triangle} />);
    await waitFor(() => expect(getByTestId('webview-geoshape-0')).toBeDefined());
  });

  it('shows the point count and area', async () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer={triangle} />);
    await waitFor(() => {
      expect(getByTestId('text-geoshape-points-0').props.children).toContain(3);
      expect(getByTestId('text-geoshape-area-0')).toBeDefined();
    });
  });

  it('withholds the area below three points', async () => {
    const { getByTestId, queryByTestId } = render(
      <GeoshapeView index={0} answer={triangle.slice(0, 2)} />,
    );
    await waitFor(() => expect(getByTestId('text-geoshape-points-0')).toBeDefined());
    expect(queryByTestId('text-geoshape-area-0')).toBeNull();
  });

  it('accepts a JSON string answer', async () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer={JSON.stringify(triangle)} />);
    await waitFor(() => expect(getByTestId('text-geoshape-points-0').props.children).toContain(3));
  });

  it('falls back to a dash for an unparseable answer', () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer="[not json" />);
    expect(getByTestId('text-answer-0').props.children).toBe('-');
  });

  it('loads the page in read-only mode', async () => {
    const { getByTestId } = render(<GeoshapeView index={0} answer={triangle} />);
    await waitFor(() => expect(getByTestId('webview-geoshape-0')).toBeDefined());
    // A pannable map inside the SectionList would swallow the scroll gesture - GEO-001 D-5.
    expect(getByTestId('webview-geoshape-0').props.scrollEnabled).toBe(false);
  });
});
