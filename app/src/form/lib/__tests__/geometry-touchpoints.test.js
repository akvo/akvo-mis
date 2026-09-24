import {
  generateValidationSchemaFieldLevel,
  generateDataPointName,
  transformMonitoringData,
} from '../index';
import { QUESTION_TYPES } from '../../../lib/constants';

/**
 * GEO-001 section 7: adding geoshape to QUESTION_TYPES alone leaves a field that renders
 * correctly and validates wrongly. These cover the quiet touchpoints - the ones with no
 * visible symptom on screen.
 */

const triangle = [
  [9.03, 38.74],
  [9.03, 38.75],
  [9.04, 38.75],
];

const geoshapeQuestion = { id: 1, name: 'boundary', type: QUESTION_TYPES.geoshape };
const geotraceQuestion = { id: 1, name: 'route', type: QUESTION_TYPES.geotrace };

/**
 * geotrace is a sibling of geoshape everywhere but rendering - an open line rather than a
 * closed ring - so every touchpoint has to list both or the field renders correctly and
 * validates wrongly.
 */
describe('geotrace shares every touchpoint with geoshape', () => {
  it('accepts an array of coordinate pairs', async () => {
    expect(await generateValidationSchemaFieldLevel(triangle, geotraceQuestion)).toEqual({
      1: true,
    });
  });

  it('accepts null when optional', async () => {
    expect(await generateValidationSchemaFieldLevel(null, geotraceQuestion)).toEqual({ 1: true });
  });

  it('rejects null when required', async () => {
    const result = await generateValidationSchemaFieldLevel(null, {
      ...geotraceQuestion,
      required: true,
    });
    expect(result[1]).not.toBe(true);
  });

  it('keeps raw coordinates out of the datapoint name', () => {
    const forms = {
      question_group: [
        {
          question: [
            { id: 1, name: 'village', type: QUESTION_TYPES.text, meta: true, order: 1 },
            { id: 2, name: 'route', type: QUESTION_TYPES.geotrace, meta: true, order: 2 },
          ],
        },
      ],
    };
    const { dpName } = generateDataPointName(forms, { 1: 'Bole', 2: triangle });
    expect(dpName).toBe('Bole');
    expect(dpName).not.toContain('9.03');
  });

  it('turns an empty answer into an empty array on resume', () => {
    const formDataJson = {
      json: JSON.stringify({ question_group: [{ question: [geotraceQuestion] }] }),
    };
    const { currentValues } = transformMonitoringData(formDataJson, { 1: '' });
    expect(currentValues[1]).toEqual([]);
  });
});

describe('geoshape validation schema (touchpoint 4)', () => {
  it('accepts an array of coordinate pairs', async () => {
    const result = await generateValidationSchemaFieldLevel(triangle, geoshapeQuestion);
    expect(result).toEqual({ 1: true });
  });

  it('accepts an empty array when the question is optional', async () => {
    const result = await generateValidationSchemaFieldLevel([], geoshapeQuestion);
    expect(result).toEqual({ 1: true });
  });

  it('accepts null when the question is optional', async () => {
    // FormNavigation hands unanswered polygon questions null, not '' - touchpoint 7.
    const result = await generateValidationSchemaFieldLevel(null, geoshapeQuestion);
    expect(result).toEqual({ 1: true });
  });

  it('rejects null when the question is required', async () => {
    const result = await generateValidationSchemaFieldLevel(null, {
      ...geoshapeQuestion,
      required: true,
    });
    expect(result[1]).not.toBe(true);
  });

  it('rejects an empty array when the question is required', async () => {
    const result = await generateValidationSchemaFieldLevel([], {
      ...geoshapeQuestion,
      required: true,
    });
    expect(result[1]).not.toBe(true);
  });

  it('does not fall through to the string schema', async () => {
    // Before the touchpoint landed an array hit `default: Yup.string()` and failed here.
    const asString = await generateValidationSchemaFieldLevel(triangle, {
      ...geoshapeQuestion,
      type: 'some_unknown_type',
    });
    expect(asString[1]).not.toBe(true);
  });
});

describe('datapoint name generation (touchpoint 5)', () => {
  const forms = {
    question_group: [
      {
        question: [
          { id: 1, name: 'village', type: QUESTION_TYPES.text, meta: true, order: 1 },
          { id: 2, name: 'boundary', type: QUESTION_TYPES.geoshape, meta: true, order: 2 },
        ],
      },
    ],
  };

  it('keeps raw coordinates out of the datapoint name', () => {
    const { dpName } = generateDataPointName(forms, { 1: 'Bole', 2: triangle });
    expect(dpName).toBe('Bole');
    expect(dpName).not.toContain('9.03');
  });
});

describe('monitoring resume (touchpoint 6)', () => {
  const formDataJson = {
    json: JSON.stringify({
      question_group: [{ question: [geoshapeQuestion] }],
    }),
  };

  it('turns an empty answer into an empty array, not an empty string', () => {
    const { currentValues } = transformMonitoringData(formDataJson, { 1: '' });
    expect(currentValues[1]).toEqual([]);
  });

  it('preserves captured points through a resume', () => {
    const { currentValues } = transformMonitoringData(formDataJson, { 1: triangle });
    expect(currentValues[1]).toEqual(triangle);
  });

  it('keeps latitude first through a resume', () => {
    const { currentValues } = transformMonitoringData(formDataJson, { 1: triangle });
    const [[lat, lng]] = currentValues[1];
    expect(lat).toBe(9.03);
    expect(lng).toBe(38.74);
  });
});
