import { completeDatapointSync, datapointSyncFinishPending } from '../sync-datapoints';

jest.mock('../../database/crud', () => ({
  crudConfig: { getConfig: jest.fn() },
  crudDataPoints: {},
  crudForms: {},
  crudJobs: { deleteJob: jest.fn(() => Promise.resolve()) },
  crudSyncQueue: { clearQueue: jest.fn(() => Promise.resolve()) },
}));

jest.mock('../api', () => ({
  post: jest.fn(() => Promise.resolve()),
  get: jest.fn(),
  setToken: jest.fn(),
}));

jest.mock('../geometry-index-writer', () => ({
  finishDatapointSync: jest.fn(),
  writeIndexFromListGeometry: jest.fn(),
}));

const { crudConfig, crudJobs } = require('../../database/crud');
const { finishDatapointSync } = require('../geometry-index-writer');

const JOB = { id: 7, attempt: 0 };

beforeEach(() => {
  jest.clearAllMocks();
});

describe('completeDatapointSync', () => {
  it('retires the job once the finish step succeeds', async () => {
    finishDatapointSync.mockResolvedValue(undefined);
    await completeDatapointSync({}, JOB);
    expect(crudJobs.deleteJob).toHaveBeenCalledWith({}, 7);
  });

  /**
   * The regression this file exists for. Deleting the job anyway left the queue complete and
   * `geometryIndexReady` at 0, and every later run retired itself as "nothing to do" — overlap
   * validation was then unavailable until a Reset.
   */
  it('leaves the job alone when the finish step throws, and rethrows', async () => {
    finishDatapointSync.mockRejectedValue(new Error('sync-complete 500'));
    await expect(completeDatapointSync({}, JOB)).rejects.toThrow('sync-complete 500');
    expect(crudJobs.deleteJob).not.toHaveBeenCalled();
  });
});

describe('datapointSyncFinishPending', () => {
  it('is true while the readiness flag has not been set', async () => {
    crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 0 });
    await expect(datapointSyncFinishPending({})).resolves.toBe(true);
  });

  it('is false once a full sync has set it', async () => {
    crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 1 });
    await expect(datapointSyncFinishPending({})).resolves.toBe(false);
  });

  it('is true when there is no config row at all', async () => {
    // Fail toward retrying rather than toward declaring the index ready.
    crudConfig.getConfig.mockResolvedValue(false);
    await expect(datapointSyncFinishPending({})).resolves.toBe(true);
  });
});
