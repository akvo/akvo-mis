import React from 'react';
import { StyleSheet } from 'react-native';
import { render, act } from '@testing-library/react-native';
import DatapointCard, { getStatus, DatapointLegend } from '../DatapointCard';
import { UIState } from '../../store';
import { dark, light } from '../../lib/theme';
import uiText from '../../lib/i18n/ui-text';

const trans = uiText.en;

describe('getStatus', () => {
  it.each([
    [{ needsRetake: true, submitted: 0 }, 'missing'],
    [{ needsRetake: true, submitted: 1, isSynced: false }, 'missing'],
    [{ submitted: 0 }, 'draft'],
    [{ submitted: 1, isSynced: false }, 'pending'],
    [{ submitted: 1, isSynced: true }, 'synced'],
  ])('%j -> %s', (item, expected) => {
    expect(getStatus(item)).toBe(expected);
  });
});

describe.each([
  ['dark', dark],
  ['light', light],
])('DatapointCard in %s mode', (mode, palette) => {
  beforeEach(() => {
    act(() => {
      UIState.update((s) => {
        s.darkModePreference = mode;
      });
    });
  });

  it('renders name, meta and a token-colored status icon', async () => {
    const item = { id: 1, name: 'HH 1', submitted: 1, isSynced: true };
    const { getByText, findByTestId } = render(
      <DatapointCard item={item} meta="Registered 28/09/2026" trans={trans} />,
    );
    expect(getByText('HH 1')).toBeTruthy();
    expect(StyleSheet.flatten(getByText('Registered 28/09/2026').props.style).color).toBe(
      palette.text.tertiary,
    );
    const icon = await findByTestId('status-synced-1');
    expect(icon.props.accessibilityLabel).toBe(trans.legendSynced);
    expect(StyleSheet.flatten(icon.props.style).color).toBe(palette.status.success);
  });

  it('explains only the icons the list shows', () => {
    const items = [
      { id: 1, submitted: 0, isSynced: false },
      { id: 2, submitted: 1, isSynced: false },
      { id: 3, submitted: 1, isSynced: true },
    ];
    const { getByText, queryByText } = render(<DatapointLegend trans={trans} items={items} />);
    expect(getByText(trans.draftText)).toBeTruthy();
    expect(getByText(trans.legendPending)).toBeTruthy();
    expect(getByText(trans.legendSynced)).toBeTruthy();
    expect(queryByText(trans.photoMissingText)).toBeNull();
  });
});
