import React from 'react';
import { BackHandler } from 'react-native';
import { render, fireEvent, act, waitFor } from '@testing-library/react-native';
import { useNavigation } from '@react-navigation/native';

import Users from '../Users';
import { UserState, UIState } from '../../store';
import { crudUsers } from '../../database/crud';

jest.mock('expo-sqlite');
jest.mock('../../database/crud');
// LogoutButton pulls in the background-sync task chain; stub the native modules.
jest.mock('expo-task-manager', () => ({ defineTask: jest.fn() }));
jest.mock('expo-background-task', () => ({ BackgroundTaskResult: { Success: 1, Failed: 2 } }));

describe('UsersPage (Profile)', () => {
  beforeAll(() => {
    UIState.update((s) => {
      s.lang = 'en';
    });
  });

  beforeEach(() => {
    crudUsers.getActiveUser.mockResolvedValue({
      id: 1,
      name: 'John Doe',
      password: '123456',
      active: 1,
      lastSyncedAt: '2026-10-26T10:00:00.000Z',
    });
    UserState.update((s) => {
      s.id = 1;
      s.name = 'John Doe';
      s.syncWifiOnly = 0;
    });
  });

  it('should show the current user profile with name and passcode', async () => {
    const mockNavigation = useNavigation();
    const { getByTestId } = render(<Users navigation={mockNavigation} />);

    await waitFor(() => {
      expect(getByTestId('profile-name')).toBeDefined();
      expect(getByTestId('profile-value-passcode').props.children).toBe('123456');
    });
  });

  it('should render the logout button instead of a user list', async () => {
    const mockNavigation = useNavigation();
    const { getByTestId, queryByTestId } = render(<Users navigation={mockNavigation} />);

    await waitFor(() => {
      expect(getByTestId('list-item-logout')).toBeDefined();
      expect(queryByTestId('users-list')).toBeNull();
    });
  });

  it('should open the logout confirmation dialog when logout pressed', async () => {
    const mockNavigation = useNavigation();
    const { getByTestId } = render(<Users navigation={mockNavigation} />);

    fireEvent.press(getByTestId('list-item-logout'));

    await waitFor(() => {
      expect(getByTestId('dialog-confirm-logout')).toBeDefined();
    });
  });

  it('should redirect to Homepage when hardware back button pressed', async () => {
    const mockNavigation = useNavigation();
    let backPressHandler;
    const spy = jest.spyOn(BackHandler, 'addEventListener').mockImplementation((_event, handler) => {
      backPressHandler = handler;
      return { remove: jest.fn() };
    });

    render(<Users navigation={mockNavigation} />);

    act(() => {
      backPressHandler();
    });

    await waitFor(() => {
      expect(mockNavigation.navigate).toHaveBeenCalledWith('Home');
    });
    spy.mockRestore();
  });

  it('should be translated when UIState.lang changed', async () => {
    const mockNavigation = useNavigation();
    const { getByText } = render(<Users navigation={mockNavigation} />);

    expect(getByText('Profile')).toBeDefined();

    act(() => {
      UIState.update((s) => {
        s.lang = 'fr';
      });
    });

    await waitFor(() => {
      expect(getByText('Profil')).toBeDefined();
    });
  });
});
