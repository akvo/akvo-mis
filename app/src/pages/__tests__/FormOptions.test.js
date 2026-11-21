import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import FormOptions from '../FormOptions';
import crudForms from '../../database/crud/crud-forms';
import { FormState, UIState } from '../../store';

// background-task imports expo-task-manager, whose native module jest-expo can't load.
jest.mock('../../lib/background-task', () => ({}));
jest.mock('../../database/crud/crud-forms');

const navigation = { push: jest.fn(), addListener: jest.fn(() => jest.fn()) };

describe('FormOptions', () => {
  beforeAll(() => {
    UIState.update((s) => {
      s.lang = 'en';
    });
    FormState.update((s) => {
      s.form = { id: 1, formId: 100, name: 'Registration' };
    });
    crudForms.getFormOptions.mockResolvedValue([
      { id: 5, formId: 200, name: 'Monitoring A', version: '2', submitted: 7, draft: 4, synced: 6 },
    ]);
  });

  it('passes submitted, draft and synced from getFormOptions to the card', async () => {
    const { getByTestId, getByText } = render(
      <FormOptions
        navigation={navigation}
        route={{ params: { id: 9, uuid: 'u-1', name: 'DP' } }}
      />,
    );
    await waitFor(() => expect(getByTestId('form-item-5')).toBeTruthy());
    expect(getByText('Monitoring A')).toBeTruthy();
    expect(getByText('7')).toBeTruthy();
    expect(getByText('4')).toBeTruthy();
    expect(getByText('6')).toBeTruthy();
    expect(getByText('View details')).toBeTruthy();
    expect(getByText('See every answer in this datapoint')).toBeTruthy();
  });
});
