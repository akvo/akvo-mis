import {
  boundingBox,
  summarizeAccuracy,
  rowFromCoordinates,
  rowFromListGeometry,
  geoshapeAnswersFromJson,
  overlapGeoshapeQuestions,
} from '../geometry-index';

const ADDIS = [
  [9.03, 38.74],
  [9.04, 38.74],
  [9.04, 38.75],
  [9.03, 38.75],
];

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
        {
          id: 988,
          type: 'geoshape',
          extra: { geoConfig: { detectOverlaps: false } },
        },
        { id: 989, type: 'input' },
      ],
    },
  ],
};

describe('geometry-index helpers', () => {
  describe('boundingBox', () => {
    it('matches the server arithmetic for a tapped ring', () => {
      expect(boundingBox(ADDIS)).toEqual({
        minLat: 9.03,
        maxLat: 9.04,
        minLon: 38.74,
        maxLon: 38.75,
      });
    });

    it('ignores the accuracy third element', () => {
      expect(boundingBox(WALKED)).toEqual({
        minLat: 9.03,
        maxLat: 9.04,
        minLon: 38.74,
        maxLon: 38.75,
      });
    });

    it('returns null for an empty ring', () => {
      expect(boundingBox([])).toBeNull();
      expect(boundingBox(null)).toBeNull();
    });
  });

  describe('summarizeAccuracy', () => {
    it('indexes a locally captured walked polygon with accuracyMeasured = 1', () => {
      // GEO-006 acceptance: this is the failure that degrades GEO-007 silently.
      expect(summarizeAccuracy(WALKED)).toEqual({
        accuracyMax: 6.8,
        accuracyMeasured: 1,
      });
    });

    it('reports not measured for a tapped ring', () => {
      expect(summarizeAccuracy(ADDIS)).toEqual({
        accuracyMax: null,
        accuracyMeasured: 0,
      });
    });

    it('takes the max of mixed walked/tapped vertices', () => {
      const mixed = [
        [9.03, 38.74, 4.2],
        [9.04, 38.74],
        [9.04, 38.75, 5.1],
      ];
      expect(summarizeAccuracy(mixed)).toEqual({
        accuracyMax: 5.1,
        accuracyMeasured: 1,
      });
    });
  });

  describe('rowFromCoordinates', () => {
    it('builds a full index row from a local answer', () => {
      const row = rowFromCoordinates(WALKED, {
        datapointId: 42,
        questionId: 987,
        repeatIndex: 0,
        name: 'Plot A',
        isComplete: true,
      });
      expect(row).toMatchObject({
        datapointId: 42,
        questionId: 987,
        repeatIndex: 0,
        name: 'Plot A',
        minLat: 9.03,
        maxLat: 9.04,
        minLon: 38.74,
        maxLon: 38.75,
        accuracyMax: 6.8,
        accuracyMeasured: 1,
        isComplete: 1,
      });
    });
  });

  describe('rowFromListGeometry', () => {
    it('stores the GEO-005 accuracy summary as given', () => {
      const row = rowFromListGeometry(
        {
          question_id: 987,
          index: 1,
          bbox: { min_lat: 9.03, max_lat: 9.04, min_lon: 38.74, max_lon: 38.75 },
          accuracy: { max: 6.8, measured: true },
        },
        { datapointId: 7, name: 'Synced', isComplete: true },
      );
      expect(row).toMatchObject({
        questionId: 987,
        repeatIndex: 1,
        accuracyMax: 6.8,
        accuracyMeasured: 1,
        minLat: 9.03,
      });
    });
  });

  describe('overlapGeoshapeQuestions / geoshapeAnswersFromJson', () => {
    it('only indexes detectOverlaps geoshape questions', () => {
      expect(overlapGeoshapeQuestions(overlapForm).map((q) => q.id)).toEqual([987]);
    });

    it('produces two rows for two repeat instances of one question (D-8)', () => {
      const answers = {
        987: ADDIS,
        '987-1': WALKED,
        988: ADDIS, // detectOverlaps off — ignored
      };
      const found = geoshapeAnswersFromJson(overlapForm, answers);
      expect(found).toHaveLength(2);
      expect(found.map((f) => f.repeatIndex).sort()).toEqual([0, 1]);
      expect(found.every((f) => f.questionId === 987)).toBe(true);
    });

    it('does no work for a form with no overlap geoshape', () => {
      const plain = {
        question_group: [{ question: [{ id: 1, type: 'input' }] }],
      };
      expect(geoshapeAnswersFromJson(plain, { 1: 'x' })).toEqual([]);
    });
  });
});
