import {
  finishDatapointSync,
  geometryIndexNeedsFullPull,
  markFormGeometryComplete,
  readGeometryTotals,
  recordGeometryTotal,
  writeIndexFromAnswers,
  writeIndexFromListGeometry,
} from '../geometry-index-writer';

jest.mock('../../database/crud', () => ({
  crudConfig: {
    updateConfig: jest.fn(() => Promise.resolve()),
    getConfig: jest.fn(() => Promise.resolve({})),
  },
  crudGeometryIndex: {
    replaceForDatapoint: jest.fn(() => Promise.resolve()),
    markFormComplete: jest.fn(() => Promise.resolve()),
  },
}));

const { crudConfig, crudGeometryIndex } = require('../../database/crud');

const WALKED = [
  [9.03, 38.74, 4.2],
  [9.04, 38.74, 6.8],
  [9.04, 38.75, 5.1],
];

const overlapForm = {
  question_group: [
    {
      question: [
        {
          id: 987,
          type: 'geoshape',
          extra: { geoConfig: { detectOverlaps: true } },
        },
      ],
    },
  ],
};

describe('geometry-index-writer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('writeIndexFromAnswers', () => {
    it('indexes a locally captured polygon with accuracyMeasured = 1', async () => {
      await writeIndexFromAnswers(
        {},
        {
          uuid: 'u-1',
          formId: 10,
          datapointId: 42,
          name: 'Local plot',
          answers: { 987: WALKED },
          formJson: overlapForm,
          isComplete: true,
        },
      );

      expect(crudGeometryIndex.replaceForDatapoint).toHaveBeenCalledWith(
        {},
        expect.objectContaining({
          uuid: 'u-1',
          formId: 10,
          rows: [
            expect.objectContaining({
              questionId: 987,
              repeatIndex: 0,
              accuracyMeasured: 1,
              accuracyMax: 6.8,
              minLat: 9.03,
            }),
          ],
        }),
      );
    });

    it('writes two rows for two repeat instances, not one (D-8)', async () => {
      await writeIndexFromAnswers(
        {},
        {
          uuid: 'u-2',
          formId: 10,
          datapointId: 43,
          name: 'Repeats',
          answers: {
            987: WALKED,
            '987-1': [
              [9.1, 38.8],
              [9.2, 38.8],
              [9.2, 38.9],
            ],
          },
          formJson: overlapForm,
        },
      );

      const { rows } = crudGeometryIndex.replaceForDatapoint.mock.calls[0][1];
      expect(rows).toHaveLength(2);
      expect(rows.map((r) => r.repeatIndex).sort()).toEqual([0, 1]);
    });

    it('clears index rows when all overlap polygons are removed', async () => {
      await writeIndexFromAnswers(
        {},
        {
          uuid: 'u-3',
          formId: 10,
          datapointId: 44,
          name: 'Empty',
          answers: {},
          formJson: overlapForm,
        },
      );

      expect(crudGeometryIndex.replaceForDatapoint).toHaveBeenCalledWith(
        {},
        { uuid: 'u-3', formId: 10, rows: [], datapointId: 44 },
      );
    });
  });

  describe('writeIndexFromListGeometry', () => {
    it('stores list accuracy as given and marks the form complete', async () => {
      await writeIndexFromListGeometry(
        {},
        {
          uuid: 'u-4',
          formId: 10,
          datapointId: 50,
          name: 'Synced',
          isComplete: true,
          geometry: [
            {
              question_id: 987,
              index: 0,
              bbox: { min_lat: 9.03, max_lat: 9.04, min_lon: 38.74, max_lon: 38.75 },
              accuracy: { max: 6.8, measured: true },
            },
          ],
        },
      );

      expect(crudGeometryIndex.replaceForDatapoint).toHaveBeenCalled();
      /**
       * The per-datapoint writer must NOT sweep the form: `isComplete` is true for every item
       * on the last page, so doing it here issued a full table UPDATE once per row.
       */
      expect(crudGeometryIndex.markFormComplete).not.toHaveBeenCalled();
    });

    it('sweeps the form exactly once, from the caller, when its last page lands', async () => {
      await markFormGeometryComplete({}, 10);
      expect(crudGeometryIndex.markFormComplete).toHaveBeenCalledTimes(1);
      expect(crudGeometryIndex.markFormComplete).toHaveBeenCalledWith({}, 10);
    });
  });

  describe('readiness and geometry totals', () => {
    /**
     * The gate that makes GEO-006 D-4 real rather than cosmetic. `/datapoint-list` is
     * cursor-based, so an upgraded device that synced yesterday receives nothing at all: the
     * sync completes instantly and, before this, declared an EMPTY post-migration index
     * trustworthy.
     */
    it('does not set readiness after a sync that was not a full pull', async () => {
      await finishDatapointSync(
        {},
        { markSyncComplete: jest.fn(), clearQueue: jest.fn(), full: false },
      );
      expect(crudConfig.updateConfig).not.toHaveBeenCalled();
    });

    it('needs a full pull until readiness is 1', async () => {
      crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 0 });
      await expect(geometryIndexNeedsFullPull({})).resolves.toBe(true);
      crudConfig.getConfig.mockResolvedValue({ geometryIndexReady: 1 });
      await expect(geometryIndexNeedsFullPull({})).resolves.toBe(false);
    });

    it('needs a full pull when there is no config row at all', async () => {
      // Fail toward pulling everything rather than toward declaring the index ready.
      crudConfig.getConfig.mockResolvedValue(false);
      await expect(geometryIndexNeedsFullPull({})).resolves.toBe(true);
    });

    it('keeps the per-form geometry total across the queue being cleared', async () => {
      crudConfig.getConfig.mockResolvedValue({ geometryTotals: '{"123":4}' });
      await recordGeometryTotal({}, 456, 9);
      expect(crudConfig.updateConfig).toHaveBeenCalledWith(
        {},
        { geometryTotals: JSON.stringify({ 123: 4, 456: 9 }) },
      );
    });

    it('does not rewrite an unchanged total', async () => {
      crudConfig.getConfig.mockResolvedValue({ geometryTotals: '{"123":4}' });
      await recordGeometryTotal({}, 123, 4);
      expect(crudConfig.updateConfig).not.toHaveBeenCalled();
    });

    it('ignores a missing geometry_total rather than storing a NaN', async () => {
      crudConfig.getConfig.mockResolvedValue({ geometryTotals: '{}' });
      await recordGeometryTotal({}, 123, undefined);
      expect(crudConfig.updateConfig).not.toHaveBeenCalled();
    });

    it('reads back an empty map when the column is corrupt', async () => {
      crudConfig.getConfig.mockResolvedValue({ geometryTotals: 'not json' });
      await expect(readGeometryTotals({})).resolves.toEqual({});
    });
  });

  describe('finishDatapointSync', () => {
    it('marks sync complete, clears the queue, then sets geometryIndexReady', async () => {
      const order = [];
      const markSyncComplete = jest.fn(async () => {
        order.push('mark');
      });
      const clearQueue = jest.fn(async () => {
        order.push('clear');
      });
      crudConfig.updateConfig.mockImplementation(async () => {
        order.push('ready');
      });

      await finishDatapointSync({}, { markSyncComplete, clearQueue, full: true });

      expect(crudConfig.updateConfig).toHaveBeenCalledWith({}, { geometryIndexReady: 1 });
      expect(markSyncComplete).toHaveBeenCalled();
      expect(clearQueue).toHaveBeenCalledWith({});
      expect(order).toEqual(['mark', 'clear', 'ready']);
    });
  });
});
