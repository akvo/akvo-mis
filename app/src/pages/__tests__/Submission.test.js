import React from 'react';
import { render, fireEvent, within } from '@testing-library/react-native';
import Submission from '../Submission';
import { crudDataPoints } from '../../database/crud';
import { FormState, UIState, UserState } from '../../store';

// background-task imports expo-task-manager, whose native module jest-expo can't load.
jest.mock('../../lib/background-task', () => ({}));
jest.mock('../../database/crud', () => ({
  crudDataPoints: {
    countFamilyDrafts: jest.fn(),
    getFamilyDrafts: jest.fn(),
    getMonitoringStats: jest.fn(),
    selectDataPointsByFormAndSubmitted: jest.fn(),
  },
  crudForms: {},
}));

const navigation = { push: jest.fn(), navigate: jest.fn(), addListener: jest.fn(() => jest.fn()) };

const row = (id, extra) => ({
  id,
  uuid: `u-${id}`,
  name: `DP ${id}`,
  submitted: 1,
  createdAt: '2026-09-01T08:00:00.000Z',
  syncedAt: '2026-09-02T08:00:00.000Z',
  json: null,
  locallyCreated: 0,
  ...extra,
});

describe('Submission sections (A19)', () => {
  beforeEach(() => {
    UIState.update((s) => {
      s.lang = 'en';
    });
    UserState.update((s) => {
      s.id = 1;
    });
    FormState.update((s) => {
      s.form = { id: 1, formId: 100, name: 'Registration', parentId: null };
      s.previousForm = null;
    });
    crudDataPoints.countFamilyDrafts.mockResolvedValue(0);
    // DP 1: downloaded, but monitored in the app later than DP 3 was registered.
    crudDataPoints.getMonitoringStats.mockResolvedValue([
      { uuid: 'u-1', submissionCount: 1, draftCount: 0, lastSubmissionAt: '2026-09-20T08:00:00Z' },
    ]);
    crudDataPoints.selectDataPointsByFormAndSubmitted.mockResolvedValue([
      row(1),
      row(2),
      row(3, { locallyCreated: 1, submittedAt: '2026-09-10T08:00:00.000Z' }),
    ]);
  });

  it('splits rows: app-created activity under Latest, newest first; the rest under Earlier', async () => {
    const { findByTestId, getByTestId, getAllByTestId } = render(
      <Submission navigation={navigation} route={{ params: { name: 'Registration' } }} />,
    );
    expect(await findByTestId('section-header-latest')).toBeTruthy();
    expect(getAllByTestId(/^submission-item-/).map((el) => el.props.testID)).toEqual([
      'submission-item-1',
      'submission-item-3',
      'submission-item-2',
    ]);
    expect(within(getByTestId('section-header-latest')).getByText('2')).toBeTruthy();
    expect(within(getByTestId('section-header-earlier')).getByText('1')).toBeTruthy();
  });

  it('collapses one section and keeps its header and count', async () => {
    const { findByTestId, queryByTestId, getByTestId } = render(
      <Submission navigation={navigation} route={{ params: { name: 'Registration' } }} />,
    );
    fireEvent.press(await findByTestId('section-header-latest'));
    expect(queryByTestId('submission-item-1')).toBeNull();
    expect(within(getByTestId('section-header-latest')).getByText('2')).toBeTruthy();
    expect(getByTestId('submission-item-2')).toBeTruthy();
  });

  it('shows Latest alone when every row has app-created activity', async () => {
    crudDataPoints.getMonitoringStats.mockResolvedValue([]);
    crudDataPoints.selectDataPointsByFormAndSubmitted.mockResolvedValue([
      row(3, { locallyCreated: 1, submittedAt: '2026-09-10T08:00:00.000Z' }),
    ]);
    const { findByText, queryByText } = render(
      <Submission navigation={navigation} route={{ params: { name: 'Registration' } }} />,
    );
    expect(await findByText('Latest submissions')).toBeTruthy();
    expect(queryByText('Earlier submissions')).toBeNull();
  });

  it('shows Earlier alone when nothing was created in the app', async () => {
    crudDataPoints.getMonitoringStats.mockResolvedValue([]);
    crudDataPoints.selectDataPointsByFormAndSubmitted.mockResolvedValue([row(1), row(2)]);
    const { findByText, queryByText } = render(
      <Submission navigation={navigation} route={{ params: { name: 'Registration' } }} />,
    );
    expect(await findByText('Earlier submissions')).toBeTruthy();
    expect(queryByText('Latest submissions')).toBeNull();
  });

  it('draws the drafts-only form groups with the same counted, collapsible header', async () => {
    crudDataPoints.getFamilyDrafts.mockResolvedValue([
      row(7, { submitted: 0, groupFormId: 100, groupName: 'Registration' }),
      row(8, { submitted: 0, groupFormId: 100, groupName: 'Registration' }),
      row(9, { submitted: 0, groupFormId: 200, groupName: 'Monitoring' }),
    ]);
    const { findByTestId, getByTestId, queryByTestId } = render(
      <Submission navigation={navigation} route={{ params: { name: 'Registration' } }} />,
    );
    fireEvent.press(await findByTestId('show-drafts-checkbox'));
    const group = await findByTestId('section-Registration');
    expect(within(group).getByText('2')).toBeTruthy();
    expect(within(getByTestId('section-Monitoring')).getByText('1')).toBeTruthy();
    fireEvent.press(group);
    expect(queryByTestId('submission-item-7')).toBeNull();
    expect(getByTestId('submission-item-9')).toBeTruthy();
  });
});
