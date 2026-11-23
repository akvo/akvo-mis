import React from 'react';
import { render, act, waitFor } from '@testing-library/react-native';
import * as Network from 'expo-network';
import SyncService from '../SyncService';
import { UIState, UserState, BuildParamsState } from '../../store';
import { backgroundTask } from '../../lib';
import crudJobs from '../../database/crud/crud-jobs';
import { crudConfig, crudDataPoints } from '../../database/crud';
import { jobStatus } from '../../lib/constants';

jest.mock('expo-sqlite', () => ({ useSQLiteContext: () => ({ mockDb: true }) }));
jest.mock('expo-network', () => ({
  getNetworkStateAsync: jest.fn(),
  NetworkStateType: { WIFI: 'WIFI', CELLULAR: 'CELLULAR' },
}));
jest.mock('@sentry/react-native', () => ({
  captureException: jest.fn(),
  captureMessage: jest.fn(),
  withScope: (cb) => cb({ setTag: jest.fn(), setExtra: jest.fn() }),
}));
jest.mock('../../lib', () => ({ backgroundTask: { syncFormSubmission: jest.fn() } }));
jest.mock('../../lib/submission-fallback', () => ({ refreshStorageWarning: jest.fn() }));
jest.mock('../../lib/geometry-index-writer', () => ({
  formsOwingFullPull: jest.fn(async () => new Set()),
  markFormGeometryComplete: jest.fn(),
  markFormGeometryReady: jest.fn(),
}));
jest.mock('../../lib/sync-datapoints', () => ({
  completeDatapointSync: jest.fn(),
  downloadDatapointsJson: jest.fn(),
  fetchFormDatapointsPageByPage: jest.fn(),
  geometryIndexNeedsFullPull: jest.fn(async () => false),
  recordGeometryTotal: jest.fn(),
}));
jest.mock('../../database/crud/crud-jobs', () => ({
  __esModule: true,
  default: {
    getActiveJob: jest.fn(),
    addJob: jest.fn(),
    deleteJob: jest.fn(),
    updateJob: jest.fn(),
  },
}));
jest.mock('../../database/crud', () => ({
  crudConfig: { getConfig: jest.fn() },
  crudDataPoints: { selectSubmissionToSync: jest.fn() },
  crudForms: { selectLatestFormVersion: jest.fn() },
  crudSyncQueue: {},
}));

const flush = () => act(async () => Promise.resolve());

describe('SyncService instant sync', () => {
  beforeEach(() => {
    UserState.update((s) => {
      s.id = 1;
    });
    BuildParamsState.update((s) => {
      s.dataSyncInterval = '3600'; // 1h: the interval timer never fires during a test
    });
    UIState.update((s) => {
      s.online = true;
      s.instantSync = 0;
    });
    Network.getNetworkStateAsync.mockResolvedValue({ type: 'WIFI', isConnected: true });
    crudConfig.getConfig.mockResolvedValue({ syncWifiOnly: false });
    crudDataPoints.selectSubmissionToSync.mockResolvedValue([{ id: 1 }]);
    crudJobs.getActiveJob.mockResolvedValue({ id: 1, status: jobStatus.PENDING, attempt: 0, user: 1 });
    crudJobs.updateJob.mockResolvedValue();
    crudJobs.deleteJob.mockResolvedValue();
    backgroundTask.syncFormSubmission.mockResolvedValue();
  });

  test('online submit: instantSync runs the upload at once', async () => {
    render(<SyncService />);
    await act(async () => {
      UIState.update((s) => {
        s.instantSync += 1;
      });
    });
    await waitFor(() => expect(backgroundTask.syncFormSubmission).toHaveBeenCalledTimes(1));
  });

  test('offline submit: instantSync does not upload, leaves it to the fallback', async () => {
    UIState.update((s) => {
      s.online = false;
    });
    render(<SyncService />);
    await act(async () => {
      UIState.update((s) => {
        s.instantSync += 1;
      });
    });
    await flush();
    expect(backgroundTask.syncFormSubmission).not.toHaveBeenCalled();
  });

  test('submit while a sync is running: the second submit is not left for the interval', async () => {
    let resolveFirst;
    backgroundTask.syncFormSubmission
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValue();

    render(<SyncService />);

    // First submit: run starts and parks on the upload
    await act(async () => {
      UIState.update((s) => {
        s.instantSync += 1;
      });
    });
    await waitFor(() => expect(backgroundTask.syncFormSubmission).toHaveBeenCalledTimes(1));

    // Second submit arrives while the lock is held — recorded, not run yet
    await act(async () => {
      UIState.update((s) => {
        s.instantSync += 1;
      });
    });
    expect(backgroundTask.syncFormSubmission).toHaveBeenCalledTimes(1);

    // First run finishes → the recorded submit is re-raised and uploaded
    await act(async () => {
      resolveFirst();
    });
    await waitFor(() => expect(backgroundTask.syncFormSubmission).toHaveBeenCalledTimes(2));
  });
});
