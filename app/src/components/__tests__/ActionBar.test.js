import React from 'react';
import { StyleSheet } from 'react-native';
import { render, act, fireEvent } from '@testing-library/react-native';
import ActionBar from '../ActionBar';
import { UIState } from '../../store';
import { dark, light } from '../../lib/theme';

describe.each([
  ['dark', dark],
  ['light', light],
])('ActionBar in %s mode', (mode, palette) => {
  beforeEach(() => {
    act(() => {
      UIState.update((s) => {
        s.darkModePreference = mode;
      });
    });
  });

  it('renders a token-colored full-width button that fires onPress', () => {
    const onPress = jest.fn();
    const { getByTestId, getByText } = render(
      <ActionBar label="New Submission" onPress={onPress} testID="new-submission-button" />,
    );
    const button = getByTestId('new-submission-button');
    expect(StyleSheet.flatten(button.props.style).backgroundColor).toBe(palette.buttonPrimary.bg);
    expect(StyleSheet.flatten(getByText('New Submission').props.style).color).toBe(
      palette.buttonPrimary.text,
    );
    expect(
      StyleSheet.flatten(getByTestId('new-submission-button-bar').props.style).backgroundColor,
    ).toBe(palette.bg.surfaceElevated3);
    fireEvent.press(button);
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
