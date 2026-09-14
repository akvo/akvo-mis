import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import FormPage from '../FormPage';
import crudDataPoints from '../../database/crud/crud-datapoints';
import { UserState, FormState } from '../../store';

jest.useFakeTimers();
jest.mock('../../database/crud/crud-datapoints');
jest.mock('expo-sqlite', () => ({ useSQLiteContext: () => ({}) }));
jest.mock('expo-crypto', () => ({ randomUUID: () => 'test-uuid' }));
// The lib barrel re-exports background-task, whose expo-task-manager import
// needs a native module jest-expo cannot provide.
// The real form fields pull in native modules (signature canvas, webview) that
// jest-expo cannot provide; the page's loading logic is what is under test.
jest.mock('../../form/FormContainer', () => {
  const { View } = jest.requireActual('react-native');
  const MockFormContainer = () => <View testID="form-container" />;
  return { __esModule: true, default: MockFormContainer };
});
jest.mock('../../lib/background-task', () => ({
  __esModule: true,
  default: {},
  repairCascadeAnswers: jest.fn(),
  defineSyncFormVersionTask: jest.fn(),
  defineSyncDatapointBackgroundTask: jest.fn(),
  defineSyncFormSubmissionTask: jest.fn(),
}));

const mockRoute = {
  params: { id: 1, name: 'Testing Form', dataPointId: 580, newSubmission: false },
};
const mockNavigation = { navigate: jest.fn(), goBack: jest.fn() };

const exampleTestForm = {
  name: 'Testing Form',
  languages: ['en'],
  defaultLanguage: 'en',
  question_group: [
    {
      name: 'registration',
      label: 'Registration',
      order: 1,
      question: [
        { id: 1, name: 'your_name', label: 'Your Name', order: 1, type: 'input', required: true },
      ],
    },
  ],
};

// A datapoint whose JSON file was missing on the server when it synced is
// stored with a NULL json column (Sentry: "Cannot read property 'replace' of
// null"). Opening it must show the empty form, not a spinner forever.
describe('FormPage with a saved datapoint that has no answers', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    UserState.update((s) => {
      s.id = 1;
    });
    FormState.update((s) => {
      s.currentValues = {};
      s.form = { json: JSON.stringify(exampleTestForm).replace(/'/g, "''") };
    });
  });

  test('renders the form empty when the stored json is null', async () => {
    crudDataPoints.selectDataPointById.mockResolvedValue({ id: 580, json: null });

    const wrapper = render(<FormPage navigation={mockNavigation} route={mockRoute} />);

    await waitFor(() => {
      expect(wrapper.getByTestId('form-container')).toBeTruthy();
    });
    expect(FormState.getRawState().currentValues).toEqual({});
  });

  test('renders the form instead of a dead spinner when reading the datapoint throws', async () => {
    crudDataPoints.selectDataPointById.mockRejectedValue(new TypeError('Cannot read property'));

    const wrapper = render(<FormPage navigation={mockNavigation} route={mockRoute} />);

    await waitFor(() => {
      expect(wrapper.getByTestId('form-container')).toBeTruthy();
    });
    expect(FormState.getRawState().currentValues).toEqual({});
  });
});
