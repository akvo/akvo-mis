import {
  OVERLAP_STATUS,
  UNAVAILABLE_CAUSE,
  overlapPreflight,
  overlapResults,
  runOverlapCheck,
  storedOverlapFailures,
} from '../overlap-check';
import { signatureOf } from '../overlap';

jest.mock('../../../database/crud', () => ({
  crudConfig: { getConfig: jest.fn() },
  crudSyncQueue: { hasIncomplete: jest.fn(), getAllProgress: jest.fn() },
  crudDataPoints: { countSyncedByFormId: jest.fn(), selectJsonByUuids: jest.fn() },
  crudGeometryIndex: { findOverlapCandidates: jest.fn() },
}));

const {
  crudConfig,
  crudSyncQueue,
  crudDataPoints,
  crudGeometryIndex,
} = require('../../../database/crud');

const FORM_ID = 123;
const QUESTION = { id: 987, required: true, extra: { geoConfig: { detectOverlaps: true } } };

const square = (west, east) => [
  [0, west],
  [0, east],
  [0.001, east],
  [0.001, west],
];

const PLOT = square(0, 0.001);

const indexRow = (overrides = {}) => ({
  uuid: 'neighbour-uuid',
  name: 'Plot A',
  questionId: QUESTION.id,
  repeatIndex: 0,
  minLat: 0,
  maxLat: 0.001,
  minLon: 0,
  maxLon: 0.001,
  accuracyMax: null,
  accuracyMeasured: 0,
  ...overrides,
});

const candidateAnswers = (points, uuid = 'neighbour-uuid') => [
  { id: 7, uuid, json: JSON.stringify({ [`${QUESTION.id}`]: points }) },
];

const healthy = () => {
  crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 1 });
  crudSyncQueue.hasIncomplete.mockResolvedValue(false);
  crudSyncQueue.getAllProgress.mockResolvedValue({ [FORM_ID]: { total: 10 } });
  crudDataPoints.countSyncedByFormId.mockResolvedValue(10);
};

beforeEach(() => {
  jest.clearAllMocks();
  healthy();
});

describe('overlapPreflight', () => {
  it('refuses when the index has never been populated', async () => {
    crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 0 });
    const result = await overlapPreflight({}, { formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.unavailable);
    expect(result.cause).toBe(UNAVAILABLE_CAUSE.indexNotReady);
    expect(result.retryable).toBe(true);
  });

  it('refuses while a datapoint sync is still unfinished', async () => {
    crudSyncQueue.hasIncomplete.mockResolvedValue(true);
    const result = await overlapPreflight({}, { formId: FORM_ID });
    expect(result.cause).toBe(UNAVAILABLE_CAUSE.syncIncomplete);
    expect(result.retryable).toBe(true);
  });

  it('refuses when a finished sync left fewer rows than the server reported', async () => {
    crudDataPoints.countSyncedByFormId.mockResolvedValue(9);
    const result = await overlapPreflight({}, { formId: FORM_ID });
    expect(result.cause).toBe(UNAVAILABLE_CAUSE.indexGapped);
    expect(result.retryable).toBe(true);
  });

  it('offers no Retry for a local database failure', async () => {
    crudConfig.getConfig.mockRejectedValue(new Error('no such table'));
    const result = await overlapPreflight({}, { formId: FORM_ID });
    expect(result.cause).toBe(UNAVAILABLE_CAUSE.localFailure);
    expect(result.retryable).toBe(false);
  });

  it('passes on a healthy device', async () => {
    const result = await overlapPreflight({}, { formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.passed);
  });
});

describe('runOverlapCheck', () => {
  it('never reaches the index when the candidate set is untrustworthy', async () => {
    crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 0 });
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.unavailable);
    expect(crudGeometryIndex.findOverlapCandidates).not.toHaveBeenCalled();
  });

  it('passes when no candidate shares the bounding box', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([]);
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.passed);
    expect(result.conflicts).toEqual([]);
    expect(crudDataPoints.selectJsonByUuids).not.toHaveBeenCalled();
  });

  it('fails on an identical polygon and names the other datapoint', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([indexRow()]);
    crudDataPoints.selectJsonByUuids.mockResolvedValue(candidateAnswers(PLOT));
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.failed);
    expect(result.conflicts).toHaveLength(1);
    expect(result.conflicts[0].percent).toBeCloseTo(100, 0);
    expect(result.conflicts[0].name).toBe('Plot A');
  });

  it('passes just under the threshold and fails just over it', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([indexRow()]);

    crudDataPoints.selectJsonByUuids.mockResolvedValue(
      candidateAnswers(square(0.00081, 0.00181)), // ~19 % of the smaller plot
    );
    const under = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(under.status).toBe(OVERLAP_STATUS.passed);

    crudDataPoints.selectJsonByUuids.mockResolvedValue(
      candidateAnswers(square(0.00079, 0.00179)), // ~21 %
    );
    const over = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(over.status).toBe(OVERLAP_STATUS.failed);
    expect(over.conflicts[0].threshold).toBe(20);
  });

  it('excludes the datapoint being edited from its own check', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([]);
    await runOverlapCheck(
      {},
      { points: PLOT, question: QUESTION, formId: FORM_ID, excludeUuid: 'self-uuid' },
    );
    expect(crudGeometryIndex.findOverlapCandidates).toHaveBeenCalledWith(
      {},
      expect.objectContaining({ excludeUuid: 'self-uuid', formId: FORM_ID, questionId: 987 }),
    );
  });

  it('reports every simultaneous overlap, not just the first', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([
      indexRow({ uuid: 'a', name: 'Plot A' }),
      indexRow({ uuid: 'b', name: 'Plot B' }),
    ]);
    crudDataPoints.selectJsonByUuids.mockResolvedValue([
      ...candidateAnswers(PLOT, 'a'),
      ...candidateAnswers(PLOT, 'b'),
    ]);
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.conflicts.map((c) => c.name)).toEqual(['Plot A', 'Plot B']);
  });

  it('reads a repeat instance by its suffixed answer key', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([indexRow({ repeatIndex: 2 })]);
    crudDataPoints.selectJsonByUuids.mockResolvedValue([
      { id: 7, uuid: 'neighbour-uuid', json: JSON.stringify({ [`${QUESTION.id}-2`]: PLOT }) },
    ]);
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.failed);
    expect(result.conflicts[0].repeatIndex).toBe(2);
  });

  it('refuses rather than passes when the index query throws', async () => {
    crudGeometryIndex.findOverlapCandidates.mockRejectedValue(new Error('no such table'));
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.status).toBe(OVERLAP_STATUS.unavailable);
    expect(result.cause).toBe(UNAVAILABLE_CAUSE.localFailure);
    expect(result.retryable).toBe(false);
  });

  it('tightens the threshold when both polygons carry measured accuracy', async () => {
    // Both walked at 1 m: a hectare-scale plot drops well below the 20 % ceiling, so an
    // overlap that a flat threshold would forgive is caught.
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([
      indexRow({ accuracyMax: 1, accuracyMeasured: 1 }),
    ]);
    crudDataPoints.selectJsonByUuids.mockResolvedValue(
      candidateAnswers(square(0.0009, 0.0019)), // ~10 %, under the flat ceiling
    );
    const walked = PLOT.map(([lat, lng]) => [lat, lng, 1]);
    const result = await runOverlapCheck(
      {},
      { points: walked, question: QUESTION, formId: FORM_ID },
    );
    expect(result.status).toBe(OVERLAP_STATUS.failed);
    expect(result.conflicts[0].adaptive).toBe(true);
    expect(result.conflicts[0].threshold).toBeLessThan(20);
  });
});

describe('the submit gate', () => {
  it('treats a never-validated polygon as failing, not passing', () => {
    const failures = storedOverlapFailures(null, QUESTION, PLOT);
    expect(failures).toHaveLength(1);
    expect(failures[0].key).toBe('overlapNotValidated');
    expect(failures[0].severity).toBe('block');
  });

  it('treats an edited polygon as never validated', () => {
    const stored = {
      status: OVERLAP_STATUS.passed,
      results: [],
      signature: signatureOf(PLOT),
    };
    expect(storedOverlapFailures(stored, QUESTION, PLOT)).toEqual([]);

    const moved = [...PLOT.slice(0, 3), [0.001, 0.0009]];
    const afterEdit = storedOverlapFailures(stored, QUESTION, moved);
    expect(afterEdit[0].key).toBe('overlapNotValidated');
  });

  it('warns rather than blocks on an optional question', () => {
    const optional = { ...QUESTION, required: false };
    expect(storedOverlapFailures(null, optional, PLOT)[0].severity).toBe('warn');
  });

  it('gives each refusal cause its own message key', () => {
    const results = overlapResults(
      { status: OVERLAP_STATUS.unavailable, cause: UNAVAILABLE_CAUSE.syncIncomplete },
      QUESTION,
    );
    expect(results[0].key).toBe('overlapUnavailable_syncIncomplete');
  });
});

describe('the failure message', () => {
  const conflict = (percent, threshold = 20) => ({
    uuid: `u-${percent}`,
    name: 'A very long generated datapoint name - with - many - segments',
    repeatIndex: 0,
    percent,
    threshold,
  });

  it('says one plot without a list when there is a single overlap', () => {
    const [result] = overlapResults(
      { status: OVERLAP_STATUS.failed, conflicts: [conflict(28.3)] },
      QUESTION,
    );
    expect(result.key).toBe('overlap');
    expect(result.params).toMatchObject({ count: 1, actual: 28.3, threshold: '20' });
  });

  it('numbers several overlaps in one line rather than repeating a line each', () => {
    const results = overlapResults(
      {
        status: OVERLAP_STATUS.failed,
        conflicts: [conflict(34), conflict(28.3), conflict(22.5)],
      },
      QUESTION,
    );
    expect(results).toHaveLength(1);
    expect(results[0].key).toBe('overlapMany');
    expect(results[0].params.list).toBe('#1 (34%), #2 (28.3%), #3 (22.5%)');
    expect(results[0].params.count).toBe(3);
  });

  it('never names the other datapoint', () => {
    const [result] = overlapResults(
      { status: OVERLAP_STATUS.failed, conflicts: [conflict(28.3)] },
      QUESTION,
    );
    expect(JSON.stringify(result.params)).not.toContain('datapoint name');
  });

  it('prints a range when the conflicts were judged at different thresholds', () => {
    // Accuracy differs per candidate, so each pair gets its own threshold (GEO-014 D-5).
    // One number would misstate why the other failed.
    const [result] = overlapResults(
      {
        status: OVERLAP_STATUS.failed,
        conflicts: [conflict(34, 9.5), conflict(28.3, 20)],
      },
      QUESTION,
    );
    expect(result.params.threshold).toBe('9.5-20');
  });

  it('numbers conflicts worst first, matching the order runOverlapCheck returns', async () => {
    crudGeometryIndex.findOverlapCandidates.mockResolvedValue([
      indexRow({ uuid: 'small', name: 'Plot small' }),
      indexRow({ uuid: 'big', name: 'Plot big' }),
    ]);
    crudDataPoints.selectJsonByUuids.mockResolvedValue([
      ...candidateAnswers(square(0.0007, 0.0017), 'small'), // ~30 %
      ...candidateAnswers(PLOT, 'big'), // 100 %
    ]);
    const result = await runOverlapCheck({}, { points: PLOT, question: QUESTION, formId: FORM_ID });
    expect(result.conflicts[0].uuid).toBe('big');
    expect(result.conflicts[0].percent).toBeGreaterThan(result.conflicts[1].percent);
  });
});
