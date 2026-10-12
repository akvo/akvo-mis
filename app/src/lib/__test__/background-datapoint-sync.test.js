import * as TaskManager from 'expo-task-manager';
import { defineSyncDatapointBackgroundTask } from '../background-task';
import { crudForms, crudSyncQueue, crudUsers } from '../../database/crud';
import { formsOwingFullPull, markFormGeometryReady } from '../geometry-index-writer';
import crudJobs from '../../database/crud/crud-jobs';
import {
  completeDatapointSync,
  fetchFormDatapointsPageByPage,
  geometryIndexNeedsFullPull,
} from '../sync-datapoints';

jest.mock('expo-task-manager', () => ({ defineTask: jest.fn() }));
jest.mock('expo-background-task', () => ({
  BackgroundTaskResult: { Success: 1, Failed: 2 },
}));
jest.mock('../../database', () => ({
  openDatabase: jest.fn(() => Promise.resolve({ closeAsync: jest.fn() })),
}));
jest.mock('../../database/crud', () => ({
  crudForms: { selectLatestFormVersion: jest.fn() },
  crudDataPoints: {},
  crudConfig: {},
  crudUsers: { getActiveUser: jest.fn() },
  crudSyncQueue: {
    getIncompleteForms: jest.fn(),
    hasEntries: jest.fn(),
    upsertQueue: jest.fn(),
    updateLastPage: jest.fn(),
  },
}));
jest.mock('../../database/crud/crud-jobs', () => ({
  getActiveJob: jest.fn(),
  updateJob: jest.fn(),
}));
jest.mock('../sync-datapoints', () => ({
  completeDatapointSync: jest.fn(() => Promise.resolve()),
  downloadDatapointsJson: jest.fn(),
  fetchFormDatapointsPageByPage: jest.fn(() => Promise.resolve()),
  geometryIndexNeedsFullPull: jest.fn(),
  recordGeometryTotal: jest.fn(),
}));
jest.mock('../geometry-index-writer', () => ({
  formsOwingFullPull: jest.fn(),
  markFormGeometryComplete: jest.fn(),
  markFormGeometryReady: jest.fn(),
}));
jest.mock('../api', () => ({ setToken: jest.fn() }));
jest.mock('../notification', () => ({}));
jest.mock('../cascades', () => ({}));

const runTask = async () => {
  defineSyncDatapointBackgroundTask();
  const [, task] = TaskManager.defineTask.mock.calls.at(-1);
  return task();
};

const job = { id: 9, attempt: 0, user: 1 };

describe('background datapoint sync with a complete queue', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    crudUsers.getActiveUser.mockResolvedValue({ id: 1, token: 't' });
    crudJobs.getActiveJob.mockResolvedValue(job);
    crudSyncQueue.hasEntries.mockResolvedValue(true);
    crudSyncQueue.getIncompleteForms.mockResolvedValue([]);
    crudForms.selectLatestFormVersion.mockResolvedValue([{ formId: 5 }, { formId: 6 }]);
    formsOwingFullPull.mockResolvedValue(new Set());
  });

  /**
   * A migrated device keeps completed rows from an earlier cursor-based sync while readiness is
   * still 0. Finishing here marked an empty or stale index ready without downloading anything.
   */
  it('leaves the job for the foreground when a full pull is still owed', async () => {
    geometryIndexNeedsFullPull.mockResolvedValue(true);
    await runTask();
    expect(completeDatapointSync).not.toHaveBeenCalled();
    expect(fetchFormDatapointsPageByPage).not.toHaveBeenCalled();
    expect(crudJobs.updateJob).not.toHaveBeenCalled();
  });

  it('leaves the job when one assigned form still owes a full pull', async () => {
    geometryIndexNeedsFullPull.mockResolvedValue(false);
    formsOwingFullPull.mockResolvedValue(new Set([6]));
    await runTask();
    expect(formsOwingFullPull).toHaveBeenCalledWith(expect.anything(), [5, 6]);
    expect(completeDatapointSync).not.toHaveBeenCalled();
  });

  it('finishes the sync once the index is already proven', async () => {
    geometryIndexNeedsFullPull.mockResolvedValue(false);
    await runTask();
    expect(completeDatapointSync).toHaveBeenCalledWith(expect.anything(), job, { full: false });
  });

  it('continues an incomplete form in the mode its pull started in', async () => {
    geometryIndexNeedsFullPull.mockResolvedValue(true);
    formsOwingFullPull.mockResolvedValue(new Set([5]));
    crudSyncQueue.getIncompleteForms.mockResolvedValue([{ formId: 5, lastPage: 2 }]);
    fetchFormDatapointsPageByPage.mockImplementation(async (formId, onPage) => {
      await onPage([], 3, 3, 0, true, 0);
    });
    await runTask();
    expect(formsOwingFullPull).toHaveBeenCalledWith(expect.anything(), [5], new Set([5]));
    expect(markFormGeometryReady).toHaveBeenCalledWith(expect.anything(), 5);
    expect(fetchFormDatapointsPageByPage).toHaveBeenCalledWith(
      5,
      expect.any(Function),
      3,
      100,
      true,
    );
    expect(completeDatapointSync).not.toHaveBeenCalled();
  });
});
