import React from 'react';
import { render, waitFor, fireEvent, act, within } from '@testing-library/react-native';
import HomePage from '../Home';
import crudForms from '../../database/crud/crud-forms';
import FormState from '../../store/forms';
import { UserState, UIState, BuildParamsState, DatapointSyncState } from '../../store';

const mockDateNow = new Date().toISOString();
const mockForms = [
  {
    id: 1,
    formId: 9001,
    version: '1.0.0',
    latest: 1,
    name: 'Form 1',
    json: JSON.stringify({ id: 9001, name: 'Form 1', question_group: [] }),
    createdAt: mockDateNow,
    submitted: 2,
    draft: 0,
    synced: 2,
    userId: 1,
  },
  {
    id: 2,
    formId: 9002,
    version: '1.0.1',
    latest: 1,
    name: 'Form 2',
    json: JSON.stringify({ id: 9002, name: 'Form 2', question_group: [] }),
    createdAt: mockDateNow,
    submitted: 1,
    draft: 3,
    synced: 0,
    userId: 1,
  },
  {
    id: 3,
    formId: 9002,
    version: '1.0.0',
    latest: 0,
    name: 'Form 2',
    json: JSON.stringify({ id: 9002, name: 'Form 2', question_group: [] }),
    createdAt: mockDateNow,
    submitted: 2,
    draft: 1,
    synced: 1,
    userId: 1,
  },
];

// background-task imports expo-task-manager, whose native module jest-expo can't load.
jest.mock('../../lib/background-task', () => ({}));
jest.mock('../../database/crud/crud-forms');
jest.mock('../../store/forms');
const mockNavigation = {
  navigate: jest.fn(),
};

describe('Homepage', () => {
  beforeAll(() => {
    UserState.update((s) => {
      s.id = 1;
      s.syncWifiOnly = 0;
    });
    UIState.update((s) => {
      s.online = true;
    });
    const mockLatestFormVersion = mockForms.filter((form) => form.latest);
    crudForms.selectLatestFormVersion.mockImplementation(() =>
      Promise.resolve(mockLatestFormVersion),
    );
  });

  test('renders correctly', async () => {
    const tree = render(<HomePage navigation={mockNavigation} />);

    await waitFor(() => expect(tree.toJSON()).toMatchSnapshot());
  });

  it('should render page title, search field and back button', async () => {
    const wrapper = render(<HomePage navigation={mockNavigation} />);

    await waitFor(() => {
      const titleElement = wrapper.getByText('Form Lists');
      expect(titleElement).toBeDefined();

      const searchField = wrapper.getByTestId('search-bar');
      expect(searchField).toBeDefined();

      const backButton = wrapper.getByTestId('button-users');
      expect(backButton).toBeDefined();
    });
  });

  it('should load last form version data from DB with form stats', async () => {
    const wrapper = render(<HomePage navigation={mockNavigation} />);

    await waitFor(() => {
      expect(crudForms.selectLatestFormVersion).toHaveBeenCalledTimes(1);
    });

    const listForm1 = within(await wrapper.findByTestId('card-touchable-1'));
    expect(listForm1.getByText('Form 1')).toBeTruthy();
    expect(listForm1.getByText('Version: 1.0.0')).toBeTruthy();
    expect(within(listForm1.getByTestId('stat-submitted')).getByText('2')).toBeTruthy();
    expect(within(listForm1.getByTestId('stat-draft')).getByText('0')).toBeTruthy();
    expect(within(listForm1.getByTestId('stat-synced')).getByText('2')).toBeTruthy();

    const listForm2 = within(wrapper.getByTestId('card-touchable-2'));
    expect(listForm2.getByText('Form 2')).toBeTruthy();
    expect(listForm2.getByText('Version: 1.0.1')).toBeTruthy();
    expect(within(listForm2.getByTestId('stat-submitted')).getByText('1')).toBeTruthy();
    expect(within(listForm2.getByTestId('stat-draft')).getByText('3')).toBeTruthy();
    expect(within(listForm2.getByTestId('stat-synced')).getByText('0')).toBeTruthy();

    const listForm3 = wrapper.queryByTestId('card-touchable-3');
    expect(listForm3).toBeFalsy();
  });

  it('should filter forms by search value', async () => {
    const wrapper = render(<HomePage navigation={mockNavigation} />);

    await waitFor(() => {
      expect(crudForms.selectLatestFormVersion).toHaveBeenCalledTimes(1);
    });

    const searchField = wrapper.getByTestId('search-bar');
    expect(searchField).toBeDefined();
    fireEvent.changeText(searchField, 'Form 1');

    const listForm1 = wrapper.queryByTestId('card-touchable-1');
    expect(listForm1).toBeTruthy();

    const listForm2 = wrapper.queryByTestId('card-touchable-2');
    expect(listForm2).toBeFalsy();

    const listForm3 = wrapper.queryByTestId('card-touchable-3');
    expect(listForm3).toBeFalsy();
  });

  it('should navigate to Users page when back button clicked', async () => {
    const wrapper = render(<HomePage navigation={mockNavigation} />);

    await waitFor(() => {
      expect(crudForms.selectLatestFormVersion).toHaveBeenCalledTimes(1);
    });

    const backButton = wrapper.getByTestId('button-users');
    expect(backButton).toBeDefined();
    fireEvent.press(backButton);

    await waitFor(() => {
      expect(mockNavigation.navigate).toHaveBeenCalledWith('Users');
    });
  });

  it('should reset form and data when app language changed', async () => {
    const { queryByTestId } = render(<HomePage navigation={mockNavigation} />);

    act(() => {
      UIState.update((s) => {
        s.lang = 'fr';
      });
      FormState.update((s) => {
        s.form = {};
      });
    });

    await waitFor(() => {
      const listForm1 = queryByTestId('card-touchable-1');
      expect(listForm1).toBeTruthy();
      const card = within(listForm1);
      expect(card.getByText('Soumis')).toBeTruthy();
      expect(card.getByText('Brouillon')).toBeTruthy();
      expect(card.getByText('Synchronisés')).toBeTruthy();
    });
    act(() => {
      UIState.update((s) => {
        s.lang = 'en';
      });
    });
  });

  describe('with no forms', () => {
    beforeEach(() => {
      crudForms.selectLatestFormVersion.mockImplementation(() => Promise.resolve([]));
    });

    afterEach(() => {
      crudForms.selectLatestFormVersion.mockImplementation(() =>
        Promise.resolve(mockForms.filter((form) => form.latest)),
      );
    });

    it('shows the empty state with an arrow to Settings', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.authenticationType = ['username', 'password'];
        });
      });
      const { findByTestId, getByText, getByTestId } = render(
        <HomePage navigation={mockNavigation} />,
      );
      expect(await findByTestId('home-empty-state')).toBeTruthy();
      expect(getByText('No forms yet')).toBeTruthy();
      expect(getByText('Add a form from Settings to start collecting data.')).toBeTruthy();
      expect(getByTestId('home-empty-state-arrow')).toBeTruthy();
    });

    it('shows the assigned-forms body and no arrow for code_assignment logins', async () => {
      act(() => {
        BuildParamsState.update((s) => {
          s.authenticationType = ['code_assignment'];
        });
      });
      const { findByTestId, getByText, queryByTestId } = render(
        <HomePage navigation={mockNavigation} />,
      );
      expect(await findByTestId('home-empty-state')).toBeTruthy();
      expect(getByText('Forms assigned to you will appear here.')).toBeTruthy();
      expect(queryByTestId('home-empty-state-arrow')).toBeNull();
    });
  });

  it('splits forms: app-created data under Latest, newest first; the rest under Earlier', async () => {
    const [form1, form2] = mockForms;
    crudForms.selectLatestFormVersion.mockImplementation(() =>
      Promise.resolve([
        { ...form1, lastActivityAt: '2026-09-01T08:00:00.000Z' },
        { ...form2, lastActivityAt: '2026-09-20T08:00:00.000Z' },
        { ...form2, id: 4, name: 'Form 4', lastActivityAt: null },
      ]),
    );
    const { findByTestId, getByTestId } = render(<HomePage navigation={mockNavigation} />);
    const latest = within(await findByTestId('form-group-latest'));
    expect(latest.getAllByTestId(/^card-touchable-/).map((el) => el.props.testID)).toEqual([
      'card-touchable-2',
      'card-touchable-1',
    ]);
    const earlier = within(getByTestId('form-group-earlier'));
    expect(earlier.getAllByTestId(/^card-touchable-/).map((el) => el.props.testID)).toEqual([
      'card-touchable-4',
    ]);
    expect(within(getByTestId('section-header-latest')).getByText('2')).toBeTruthy();
    expect(within(getByTestId('section-header-earlier')).getByText('1')).toBeTruthy();
    crudForms.selectLatestFormVersion.mockImplementation(() =>
      Promise.resolve(mockForms.filter((form) => form.latest)),
    );
  });

  it('shows Latest alone when every form has app-created data', async () => {
    crudForms.selectLatestFormVersion.mockImplementation(() =>
      Promise.resolve(
        mockForms
          .filter((form) => form.latest)
          .map((form) => ({ ...form, lastActivityAt: '2026-09-20T08:00:00.000Z' })),
      ),
    );
    const { findByText, queryByText } = render(<HomePage navigation={mockNavigation} />);
    expect(await findByText('Latest submissions')).toBeTruthy();
    expect(queryByText('Earlier submissions')).toBeNull();
    crudForms.selectLatestFormVersion.mockImplementation(() =>
      Promise.resolve(mockForms.filter((form) => form.latest)),
    );
  });

  it('shows Earlier alone when no form has app-created data', async () => {
    const { findByText, queryByText } = render(<HomePage navigation={mockNavigation} />);
    expect(await findByText('Earlier submissions')).toBeTruthy();
    expect(queryByText('Latest submissions')).toBeNull();
  });

  it('shows the Add form row only when the login can add forms', async () => {
    act(() => {
      BuildParamsState.update((s) => {
        s.authenticationType = ['username', 'password'];
      });
    });
    const { findByTestId } = render(<HomePage navigation={mockNavigation} />);
    fireEvent.press(await findByTestId('home-add-form'));
    expect(mockNavigation.navigate).toHaveBeenCalledWith('AddNewForm', {});
  });

  it('does not trigger sync when syncWifiOnly is true & network type cellular', async () => {
    act(() => {
      UserState.update((s) => {
        s.syncWifiOnly = 1;
      });
      UIState.update((s) => {
        s.networkType = 'CELLULAR';
        s.isOnline = true;
      });
    });

    render(<HomePage navigation={mockNavigation} />);

    act(() => {
      UIState.update((s) => {
        s.triggerSync = true;
      });
    });

    expect(DatapointSyncState.getRawState().inProgress).toBeFalsy();
  });
});
