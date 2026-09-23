import {
  finishDatapointSync,
  writeIndexFromAnswers,
  writeIndexFromListGeometry,
} from '../geometry-index-writer';

jest.mock('../../database/crud', () => ({
  crudConfig: {
    updateConfig: jest.fn(() => Promise.resolve()),
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
        { uuid: 'u-3', formId: 10, rows: [] },
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
      expect(crudGeometryIndex.markFormComplete).toHaveBeenCalledWith({}, 10);
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

      await finishDatapointSync({}, { markSyncComplete, clearQueue });

      expect(crudConfig.updateConfig).toHaveBeenCalledWith({}, { geometryIndexReady: 1 });
      expect(markSyncComplete).toHaveBeenCalled();
      expect(clearQueue).toHaveBeenCalledWith({});
      expect(order).toEqual(['mark', 'clear', 'ready']);
    });
  });
});
