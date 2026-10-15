import React from 'react';
import { render, act, fireEvent, waitFor } from '@testing-library/react-native';
import Language from '../Language';
import { FormState, UIState } from '../../../store';
import { crudConfig } from '../../../database/crud';

// background-task imports expo-task-manager, whose native module jest-expo can't load.
jest.mock('../../../lib/background-task', () => ({}));

jest.mock('@react-navigation/native');
jest.mock('expo-sqlite', () => ({
  ...jest.requireActual('expo-sqlite'),
  useSQLiteContext: jest.fn().mockReturnValue({}),
}));
jest.mock('../../../database/crud', () => ({
  crudConfig: { updateConfig: jest.fn().mockResolvedValue(true) },
}));

describe('Language', () => {
  beforeEach(() => {
    act(() => {
      UIState.update((s) => {
        s.lang = 'en';
      });
      FormState.update((s) => {
        s.lang = 'en';
      });
    });
  });

  it('checks the active language', () => {
    const { getByTestId } = render(<Language />);
    expect(getByTestId('language-option-en').props.accessibilityState.checked).toBe(true);
    expect(getByTestId('language-option-fr').props.accessibilityState.checked).toBe(false);
  });

  it('switches interface and question language, and saves it', async () => {
    const { getByTestId, getByText } = render(<Language />);
    fireEvent.press(getByTestId('language-option-fr'));

    await waitFor(() => {
      expect(UIState.getRawState().lang).toBe('fr');
      expect(FormState.getRawState().lang).toBe('fr');
      expect(crudConfig.updateConfig).toHaveBeenCalledWith({}, { lang: 'fr' });
    });
    expect(getByText('Langue')).toBeTruthy();
  });
});
