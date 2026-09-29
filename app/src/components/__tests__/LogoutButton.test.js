import React from 'react';
import { render, renderHook, fireEvent, act, waitFor } from '@testing-library/react-native';
import { useNavigation } from '@react-navigation/native';

import LogoutButton from '../LogoutButton';
import { AuthState, UserState } from '../../store';
import { cascades, i18n } from '../../lib';

jest.mock('@react-navigation/native');
jest.mock('expo-sqlite');
jest.mock('../../lib', () => ({
  cascades: {
    dropFiles: jest.fn(async () => ['file.sqlite', 'file.sqlite-journal']),
  },
  i18n: {
    text: jest.fn(),
  },
  api: {
    setToken: jest.fn(),
  },
}));

describe('LogoutButton', () => {
  beforeAll(() => {
    i18n.text.mockReturnValue({
      settingsResetTitle: 'Reset (clear all data)',
      settingsResetDesc: 'Erases every local user, form and datapoint',
    });
  });

  test('render correctly', () => {
    const { getByText, getByTestId } = render(<LogoutButton />);

    const logoutItem = getByTestId('list-item-logout');
    expect(logoutItem).toBeDefined();

    const logoutText = getByText('Reset (clear all data)');
    expect(logoutText).toBeDefined();
  });

  test('state and session still exist when aborted logout', async () => {
    const mockToken = 'Bearer mockToken';
    act(() => {
      AuthState.update((s) => {
        s.token = mockToken;
      });
    });

    const { getByTestId } = render(<LogoutButton />);
    const logoutEl = getByTestId('list-item-logout');
    fireEvent.press(logoutEl);

    const dialogEl = getByTestId('dialog-confirm-logout');
    expect(dialogEl).toBeDefined();
    const cancelEl = getByTestId('dialog-button-no');
    expect(cancelEl).toBeDefined();
    fireEvent.press(cancelEl);

    await waitFor(async () => {
      const { result } = renderHook(() => AuthState.useState());
      const { token } = result.current;
      expect(token).toEqual(mockToken);
    });
  });

  test('clear state and all tables on successfull logout', async () => {
    const mockToken = 'Bearer mockToken';

    act(() => {
      AuthState.update((s) => {
        s.token = mockToken;
      });
    });

    const { getByTestId } = render(<LogoutButton />);
    const logoutEl = getByTestId('list-item-logout');
    fireEvent.press(logoutEl);

    const dialogEl = getByTestId('dialog-confirm-logout');
    expect(dialogEl).toBeDefined();
    const yesEl = getByTestId('dialog-button-yes');
    expect(yesEl).toBeDefined();
    fireEvent.press(yesEl);

    await act(async () => {
      await cascades.dropFiles();
      AuthState.update((s) => {
        s.token = null;
      });
    });

    await waitFor(() => {
      const { result } = renderHook(() => AuthState.useState());
      const { token } = result.current;
      expect(token).toBe(null);

      const { result: userStateRef } = renderHook(() => UserState.useState());
      const { id, name, password } = userStateRef.current;
      expect(id).toBe(null);
      expect(name).toBe(null);
      expect(password).toBe('');

      const { result: navigationRef } = renderHook(() => useNavigation());
      const navigation = navigationRef.current;
      expect(navigation.navigate).toHaveBeenCalledWith('GetStarted');
    });
  });
});
