import React from 'react';
import { StyleSheet } from 'react-native';
import { render, act, fireEvent } from '@testing-library/react-native';
import SettingRow from '../SettingRow';
import MessageNote from '../MessageNote';
import { getLevelTier } from '../LevelIcon';
import { UIState } from '../../store';
import { dark, light } from '../../lib/theme';

const colorOf = (el) => StyleSheet.flatten(el.props.style).color;

describe('getLevelTier', () => {
  it.each([
    ['accuracy', 1, 1],
    ['accuracy', 2, 1],
    ['accuracy', 3, 2],
    ['accuracy', 4, 3],
    ['accuracy', 5, 3],
    ['imageQuality', 'low', 1],
    ['imageQuality', 'medium', 2],
    ['imageQuality', 'high', 3],
    ['imageQuality', 'original', 3],
    ['accuracy', 99, null],
  ])('%s %s → %s bars', (kind, level, tier) => {
    expect(getLevelTier(kind, level)).toBe(tier);
  });
});

describe.each([
  ['dark', dark],
  ['light', light],
])('Settings primitives in %s mode', (mode, palette) => {
  beforeEach(() => {
    act(() => {
      UIState.update((s) => {
        s.darkModePreference = mode;
      });
    });
  });

  it('renders a value row with token colors', () => {
    const { getByText } = render(
      <SettingRow label="Sync Interval" description="How often" control="value" value="60 s" />,
    );
    expect(colorOf(getByText('Sync Interval'))).toBe(palette.text.primary);
    expect(colorOf(getByText('How often'))).toBe(palette.text.tertiary);
    expect(colorOf(getByText('60 s'))).toBe(palette.text.secondary);
  });

  it('renders a level chip with its tier icon', () => {
    const { getByText, UNSAFE_getByProps: getByProps } = render(
      <SettingRow
        label="Accuracy level"
        control="level"
        value="Balanced"
        level={{ kind: 'accuracy', value: 3 }}
      />,
    );
    expect(getByText('Balanced')).toBeTruthy();
    expect(getByProps({ name: 'signal-cellular-2' })).toBeTruthy();
  });

  it('passes toggles through as booleans', () => {
    const onValueChange = jest.fn();
    const { getByTestId } = render(
      <SettingRow
        label="Sync Wi-Fi"
        control="toggle"
        value
        onValueChange={onValueChange}
        switchTestID="row-switch"
      />,
    );
    fireEvent(getByTestId('row-switch'), 'valueChange', false);
    expect(onValueChange).toHaveBeenCalledWith(false);
  });

  it('colors a danger note as an error and fires onPress', () => {
    const onPress = jest.fn();
    const { getByText, getByTestId } = render(
      <MessageNote tone="danger" lines={['Reset']} onPress={onPress} testID="note" />,
    );
    expect(colorOf(getByText('Reset'))).toBe(palette.input.errorText);
    fireEvent.press(getByTestId('note'));
    expect(onPress).toHaveBeenCalled();
  });
});
