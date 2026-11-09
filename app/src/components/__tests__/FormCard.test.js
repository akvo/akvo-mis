import React from 'react';
import { StyleSheet } from 'react-native';
import { render, act } from '@testing-library/react-native';
import FormCard from '../FormCard';
import { UIState } from '../../store';
import { dark, light } from '../../lib/theme';

const colorOf = (el) => StyleSheet.flatten(el.props.style).color;

describe.each([
  ['dark', dark],
  ['light', light],
])('FormCard in %s mode', (mode, palette) => {
  beforeEach(() => {
    act(() => {
      UIState.update((s) => {
        s.darkModePreference = mode;
        s.lang = 'en';
      });
    });
  });

  it.each(['home', 'monitoring'])('%s variant colors counts per D-2', (variant) => {
    const { getByText } = render(
      <FormCard
        variant={variant}
        title="Form A"
        version="1.0.0"
        submitted={5}
        draft={3}
        synced={1}
      />,
    );
    expect(getByText('Form A')).toBeTruthy();
    expect(getByText('Version: 1.0.0')).toBeTruthy();
    expect(getByText('Submitted')).toBeTruthy();
    expect(getByText('Draft')).toBeTruthy();
    expect(getByText('Synced')).toBeTruthy();
    expect(colorOf(getByText('5'))).toBe(palette.text.primary);
    expect(colorOf(getByText('3'))).toBe(palette.status.warning);
    expect(colorOf(getByText('1'))).toBe(palette.status.success);
  });

  it('shows the sync progress bar only while syncing', () => {
    const { queryByTestId, rerender } = render(<FormCard title="Form A" version="1" />);
    expect(queryByTestId('sync-progress-bar')).toBeNull();
    rerender(<FormCard title="Form A" version="1" syncing syncProgress={40} />);
    expect(queryByTestId('sync-progress-bar')).toBeTruthy();
  });
});
