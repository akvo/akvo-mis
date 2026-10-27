import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { route } from '@react-navigation/native';
import SettingsForm from '../SettingsForm';
import { config } from '../config';
import { BuildParamsState } from '../../../store';
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

describe('SettingsForm', () => {
  it('renders every field of the page under its section, with the note', () => {
    route.params = { id: 1, name: 'Advanced Settings' };
    const findConfig = config.find((c) => c?.id === 1);

    const { getByText, getByTestId } = render(<SettingsForm route={route} />);

    expect(getByTestId('settings-form-switch-3')).toBeDefined();
    expect(getByText('Server')).toBeDefined();
    expect(getByText('Synchronization')).toBeDefined();
    expect(getByTestId('settings-note')).toBeDefined();
    findConfig.fields.forEach((f) => {
      expect(getByText(f.label)).toBeDefined();
    });
  });

  it('shows no note on Geolocation', () => {
    route.params = { id: 2, name: 'Geolocation Settings' };
    const { queryByTestId, getByText } = render(<SettingsForm route={route} />);
    expect(getByText('Location')).toBeDefined();
    expect(queryByTestId('settings-note')).toBeNull();
  });

  it('stores an edited value in the state and the database', async () => {
    route.params = { id: 1, name: 'Advanced Settings' };
    const { getByTestId } = render(<SettingsForm route={route} />);

    fireEvent.press(getByTestId('settings-form-item-2'));
    expect(getByTestId('settings-form-dialog')).toBeDefined();

    fireEvent.changeText(getByTestId('settings-form-input'), '500');
    fireEvent.press(getByTestId('settings-form-dialog-ok'));

    await waitFor(() => {
      expect(BuildParamsState.getRawState().dataSyncInterval).toBe('500');
      expect(crudConfig.updateConfig).toHaveBeenCalledWith({}, { syncInterval: '500' });
    });
  });
});
