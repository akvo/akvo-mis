import { QUESTION_TYPES } from './constants';
import { vertexAccuracy } from '../form/lib/gps-vertex';

/**
 * Bounding box of `[[lat, lon], …]` — same arithmetic as the backend's
 * `bounding_box()` in `v1_mobile/geometry.py`. Ignores an optional third
 * (accuracy) element.
 *
 * @returns {{ minLat: number, maxLat: number, minLon: number, maxLon: number }|null}
 */
export const boundingBox = (coordinates) => {
  if (!Array.isArray(coordinates) || coordinates.length === 0) {
    return null;
  }
  const latitudes = [];
  const longitudes = [];
  coordinates.forEach((point) => {
    if (!Array.isArray(point) || point.length < 2) {
      return;
    }
    const lat = Number(point[0]);
    const lon = Number(point[1]);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      latitudes.push(lat);
      longitudes.push(lon);
    }
  });
  if (!latitudes.length) {
    return null;
  }
  return {
    minLat: Math.min(...latitudes),
    maxLat: Math.max(...latitudes),
    minLon: Math.min(...longitudes),
    maxLon: Math.max(...longitudes),
  };
};

/**
 * Per-polygon accuracy summary (GEO-014 D-10).
 *
 * A locally captured walked polygon must land with `accuracyMeasured = 1` —
 * that is the failure that degrades GEO-007 silently if omitted (GEO-006).
 *
 * @returns {{ accuracyMax: number|null, accuracyMeasured: 0|1 }}
 */
export const summarizeAccuracy = (coordinates) => {
  if (!Array.isArray(coordinates)) {
    return { accuracyMax: null, accuracyMeasured: 0 };
  }
  const measured = coordinates
    .map((vertex) => vertexAccuracy(vertex))
    .filter((metres) => metres !== null);
  if (!measured.length) {
    return { accuracyMax: null, accuracyMeasured: 0 };
  }
  return {
    accuracyMax: Math.max(...measured),
    accuracyMeasured: 1,
  };
};

/**
 * Map a GEO-005 list `geometry[]` entry (snake_case) onto an index row.
 * Accuracy is stored as given; missing summary → not measured.
 */
export const rowFromListGeometry = (entry, { datapointId, name, isComplete }) => {
  const bbox = entry?.bbox || {};
  const accuracy = entry?.accuracy || {};
  return {
    datapointId,
    questionId: entry.question_id,
    repeatIndex: entry.index ?? 0,
    name,
    minLat: bbox.min_lat,
    maxLat: bbox.max_lat,
    minLon: bbox.min_lon,
    maxLon: bbox.max_lon,
    accuracyMax: typeof accuracy.max === 'number' ? accuracy.max : null,
    accuracyMeasured: accuracy.measured ? 1 : 0,
    isComplete: isComplete ? 1 : 0,
  };
};

/**
 * Build an index row from a local geoshape answer (compute bbox + summary).
 */
export const rowFromCoordinates = (
  coordinates,
  { datapointId, questionId, repeatIndex, name, isComplete },
) => {
  const bbox = boundingBox(coordinates);
  if (!bbox) {
    return null;
  }
  const accuracy = summarizeAccuracy(coordinates);
  return {
    datapointId,
    questionId,
    repeatIndex: repeatIndex ?? 0,
    name,
    ...bbox,
    ...accuracy,
    isComplete: isComplete ? 1 : 0,
  };
};

/**
 * Geoshape questions on this form that opted into overlap detection.
 * Matches the backend gate in `enabled_geoshape_question_ids`.
 */
export const overlapGeoshapeQuestions = (formJson) => {
  const groups = formJson?.question_group || [];
  const questions = [];
  groups.forEach((group) => {
    (group.question || []).forEach((q) => {
      if (q?.type === QUESTION_TYPES.geoshape && q?.extra?.geoConfig?.detectOverlaps === true) {
        questions.push(q);
      }
    });
  });
  return questions;
};

/**
 * Pull every overlap-enabled geoshape answer out of a datapoint's answers blob.
 * Repeat keys are `"questionId-n"`; the bare id is repeat index 0.
 */
export const geoshapeAnswersFromJson = (formJson, answers) => {
  if (!answers || typeof answers !== 'object') {
    return [];
  }
  const questions = overlapGeoshapeQuestions(formJson);
  if (!questions.length) {
    return [];
  }
  const found = [];
  questions.forEach((q) => {
    const qId = `${q.id}`;
    Object.keys(answers).forEach((key) => {
      const keyStr = `${key}`;
      let repeatIndex = null;
      if (keyStr === qId) {
        repeatIndex = 0;
      } else if (keyStr.startsWith(`${qId}-`)) {
        const suffix = keyStr.slice(qId.length + 1);
        const parsed = parseInt(suffix, 10);
        if (`${parsed}` === suffix && Number.isFinite(parsed)) {
          repeatIndex = parsed;
        }
      }
      if (repeatIndex === null) {
        return;
      }
      const coordinates = answers[key];
      if (!Array.isArray(coordinates) || coordinates.length === 0) {
        return;
      }
      found.push({ questionId: q.id, repeatIndex, coordinates });
    });
  });
  return found;
};
