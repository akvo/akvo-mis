import { completeDatapointSync } from '../sync-datapoints';

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
  geometryIndexNeedsFullPull: jest.fn(),
  recordGeometryTotal: jest.fn(),
  writeIndexFromListGeometry: jest.fn(),
}));

const { crudJobs } = require('../../database/crud');
const { finishDatapointSync } = require('../geometry-index-writer');

const JOB = { id: 7, attempt: 0 };

beforeEach(() => {
  jest.clearAllMocks();
});

describe('completeDatapointSync', () => {
  it('passes the full-pull flag through to the finish step', async () => {
    finishDatapointSync.mockResolvedValue(undefined);
    await completeDatapointSync({}, JOB, { full: true });
    expect(finishDatapointSync).toHaveBeenCalledWith({}, expect.objectContaining({ full: true }));
  });

  it('defaults to NOT full, so an ordinary sync cannot flip readiness', async () => {
    finishDatapointSync.mockResolvedValue(undefined);
    await completeDatapointSync({}, JOB);
    expect(finishDatapointSync).toHaveBeenCalledWith({}, expect.objectContaining({ full: false }));
  });

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
