/**
 * The database half of overlap detection: is the candidate set trustworthy, and what does it
 * contain?
 *
 * Split from `overlap.js` so the maths stays testable without a database. Reasoning:
 * GEO-007 D-10 (refuse, never caveat-pass) and GEO-006 D-5 (the index carries bounding boxes,
 * not coordinates).
 */
import {
  crudConfig,
  crudDataPoints,
  crudGeometryIndex,
  crudJobs,
  crudSyncQueue,
} from '../../database/crud';
import { jobStatus, SYNC_DATAPOINT_JOB_NAME } from '../../lib/constants';
import { boundingBox, summarizeAccuracy } from '../../lib/geometry-index';
import { readGeometryTotals } from '../../lib/geometry-index-writer';
import { polygonArea } from './geometry';
import {
  OVERLAP_CONFIG_KEY,
  OVERLAP_RULE_KEY,
  adaptiveThreshold,
  answerKey,
  baseQuestionId,
  overlapPercent,
  signatureOf,
} from './overlap';
import { resolveSeverity } from './polygon-rules';

/** Reported like a rule so the report renders one list, not three special cases. */
export const UNAVAILABLE_RULE_KEY = 'overlapUnavailable';
export const NOT_VALIDATED_RULE_KEY = 'overlapNotValidated';
/** One overlap and several read differently enough to deserve separate sentences. */
export const OVERLAP_MANY_RULE_KEY = 'overlapMany';

export const OVERLAP_STATUS = {
  notValidated: 'notValidated',
  checking: 'checking',
  passed: 'passed',
  failed: 'failed',
  unavailable: 'unavailable',
};

/**
 * Why the candidate set cannot be trusted. Each of these would otherwise report a confident
 * "no overlap", which is why they share one refuse branch rather than falling through (D-10).
 */
export const UNAVAILABLE_CAUSE = {
  indexNotReady: 'indexNotReady',
  syncRunning: 'syncRunning',
  syncIncomplete: 'syncIncomplete',
  indexGapped: 'indexGapped',
  /** The index and `datapoints` disagree. A resync rebuilds both, so this is recoverable. */
  indexDrifted: 'indexDrifted',
  /** SQLite itself refused — a missing table, a dead handle. Syncing cannot mend that. */
  localFailure: 'localFailure',
};

/** Retry only helps where sync can close the gap. A corrupt database cannot be tapped better. */
const RETRYABLE = [
  UNAVAILABLE_CAUSE.indexNotReady,
  UNAVAILABLE_CAUSE.syncIncomplete,
  UNAVAILABLE_CAUSE.indexGapped,
  UNAVAILABLE_CAUSE.indexDrifted,
];

const unavailable = (cause) => ({
  status: OVERLAP_STATUS.unavailable,
  cause,
  retryable: RETRYABLE.includes(cause),
  conflicts: [],
});

/**
 * Is the local candidate set complete enough to draw a conclusion from?
 *
 * Runs before the bbox query, once, and is the only thing standing between an empty index and a
 * green tick. Order matters: the cheapest and most decisive check first, so an upgraded device
 * that has not resynced never reaches the row-count query.
 */
export const overlapPreflight = async (db, { formId } = {}) => {
  try {
    const config = await crudConfig.getConfig(db);
    if (!config || config.geometryIndexReady !== 1) {
      return unavailable(UNAVAILABLE_CAUSE.indexNotReady);
    }
    /**
     * A sync in flight is not visible in the queue yet.
     *
     * `finishDatapointSync` clears the queue when a sync completes, and the next sync does not
     * write a row until its first page lands — seconds later on a field connection. In that
     * window `hasIncomplete()` is false and readiness is still `1` from last time, so Validate
     * measured against the pre-refresh index and returned a confident pass. The Retry button
     * leads straight into it: it kicks a sync and invites the enumerator to press Validate
     * again. The job is ON_PROGRESS for the whole of that window, so gate on the job.
     *
     * On `ON_PROGRESS` only, deliberately. A PENDING job is one that has not started — offline,
     * or waiting for the next tick — and the index then still reflects the last completed sync,
     * which is the ordinary offline state this whole feature exists to serve. Blocking on
     * PENDING would refuse validation for `MAX_ATTEMPT` ticks every time an enumerator pressed
     * sync out of coverage. A job left ON_PROGRESS by a killed app does block until the next
     * sync run resets it, which is the safe direction and clears itself.
     */
    const syncJob = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);
    if (syncJob?.status === jobStatus.ON_PROGRESS) {
      return unavailable(UNAVAILABLE_CAUSE.syncRunning);
    }
    if (await crudSyncQueue.hasIncomplete(db)) {
      return unavailable(UNAVAILABLE_CAUSE.syncIncomplete);
    }
    /**
     * A sync that reported itself finished can still have gaps — a page that 200'd with the web
     * app's index.html, a datapoint whose json fetch was skipped, a datapoint that landed
     * without one of its several polygons.
     *
     * Compared against `geometry_total`: the server's cursor-free count of geoshape ANSWERS,
     * which the backend publishes for exactly this check and warns must not be confused with
     * the page `total`. An earlier version compared datapoint counts from the sync queue, which
     * could not see a single missing polygon inside a datapoint that did arrive — and read as
     * "complete" the moment the queue was cleared, which is every time it mattered.
     */
    const totals = await readGeometryTotals(db);
    const expected = totals?.[`${formId}`];
    if (Number.isFinite(expected) && expected > 0) {
      const indexed = await crudGeometryIndex.countByForm(db, formId);
      if (indexed < expected) {
        return unavailable(UNAVAILABLE_CAUSE.indexGapped);
      }
    }
    return { status: OVERLAP_STATUS.passed, conflicts: [] };
  } catch {
    return unavailable(UNAVAILABLE_CAUSE.localFailure);
  }
};

/**
 * Coordinates for the candidates that survived the bbox filter.
 *
 * One query for every survivor, then one parse each — 5–50 of them. This is what keeps peak
 * memory constant in the size of the form rather than linear in it: the other 9,950 datapoints
 * are never materialised (GEO-006 D-5, D-7).
 */
const coordinatesForCandidates = async (db, candidates) => {
  const ids = [...new Set(candidates.map((row) => row.datapointId).filter(Boolean))];
  if (!ids.length) {
    return {};
  }
  const rows = await crudDataPoints.selectJsonByIds(db, ids);
  return rows.reduce((acc, row) => {
    try {
      acc[row.id] = typeof row.json === 'string' ? JSON.parse(row.json) : row.json;
    } catch {
      /**
       * A candidate whose answers will not parse cannot be measured. It stays in the map as
       * `null` rather than being left out, so the caller can tell "unparseable" apart from
       * "never fetched" — both refuse, but only one of them means the index has drifted.
       */
      acc[row.id] = null;
    }
    return acc;
  }, {});
};

const conflictFrom = (row, candidatePoints, points, geoConfig) => {
  const percent = overlapPercent(points, candidatePoints);
  if (!(percent > 0)) {
    return null;
  }
  const local = summarizeAccuracy(points);
  const { threshold, adaptive } = adaptiveThreshold({
    accA: local.accuracyMeasured ? local.accuracyMax : null,
    accB: row.accuracyMeasured ? row.accuracyMax : null,
    areaA: polygonArea(points),
    areaB: polygonArea(candidatePoints),
    geoConfig,
  });
  if (percent < threshold) {
    return null;
  }
  return {
    uuid: row.uuid,
    name: row.name || null,
    questionId: row.questionId,
    repeatIndex: row.repeatIndex ?? 0,
    /**
     * Strings, not numbers, and deliberately. `Number((34).toFixed(1))` is `34`, so a list read
     * `#1 (34%), #2 (28.3%)` — the same quantity printed two ways in one sentence. Sorting and
     * comparison are done before this point, on the raw values.
     */
    percent: percent.toFixed(1),
    threshold: threshold.toFixed(1),
    rawPercent: percent,
    adaptive,
  };
};

/**
 * Run the overlap check for one polygon.
 *
 * `formId` is the form whose datapoints are candidates, and the caller chooses it: GEO-007 D-6
 * wants **registration** plots, so a monitoring form must pass its parent's id rather than its
 * own. Resolving that here would mean guessing at a form relationship this function cannot see.
 *
 * `excludeUuid` is the datapoint being edited — without it every edit overlaps itself by 100 %.
 */
export const runOverlapCheck = async (
  db,
  { points, question, formId, excludeUuid = null } = {},
) => {
  if (!Array.isArray(points) || points.length < 3) {
    return { status: OVERLAP_STATUS.passed, conflicts: [] };
  }
  const preflight = await overlapPreflight(db, { formId });
  if (preflight.status === OVERLAP_STATUS.unavailable) {
    return preflight;
  }
  const bbox = boundingBox(points);
  if (!bbox) {
    return { status: OVERLAP_STATUS.passed, conflicts: [] };
  }
  try {
    const candidates = await crudGeometryIndex.findOverlapCandidates(db, {
      formId,
      // Repeat instances arrive as "987-1"; the index stores 987 + repeatIndex (see
      // `baseQuestionId`). `row.questionId` below needs no stripping — it comes FROM the index.
      questionId: baseQuestionId(question?.id),
      ...bbox,
      excludeUuid,
    });
    if (!candidates?.length) {
      return { status: OVERLAP_STATUS.passed, conflicts: [] };
    }
    const answersById = await coordinatesForCandidates(db, candidates);
    const geoConfig = question?.extra?.geoConfig;
    /**
     * Keyed by `datapointId`, the local row id — never by uuid. A uuid identifies a plot, and
     * monitoring datapoints inherit their registration's, so a uuid-keyed map collapsed a whole
     * form family into one entry and handed back whichever row the query returned last.
     */
    let drifted = false;
    const conflicts = candidates.reduce((acc, row) => {
      const answers = answersById[row.datapointId];
      if (!answers) {
        /**
         * The index named a candidate whose answers are not on this device. GEO-006 D-6 makes
         * `geometry_index` a subset of `datapoints` by writing both in one transaction, so this
         * means the two have drifted — and measuring what is left would report "no overlap" for
         * a plot nobody looked at. Refuse instead (D-10).
         */
        drifted = true;
        return acc;
      }
      const candidatePoints = answers[answerKey(row.questionId, row.repeatIndex)];
      if (!Array.isArray(candidatePoints)) {
        // Indexed as a geoshape answer, absent from the answers: drift again, not thin data.
        drifted = true;
        return acc;
      }
      if (candidatePoints.length < 3) {
        /**
         * A stored answer of one or two vertices. `boundingBox` accepts those, so it can be
         * indexed, but it encloses no area and cannot overlap anything. That is a neighbour's
         * data quality, not our corruption, so it is skipped rather than blocking this
         * enumerator behind a message about resetting the app.
         */
        return acc;
      }
      const conflict = conflictFrom(row, candidatePoints, points, geoConfig);
      return conflict ? [...acc, conflict] : acc;
    }, []);
    if (drifted) {
      return unavailable(UNAVAILABLE_CAUSE.indexDrifted);
    }
    return {
      status: conflicts.length ? OVERLAP_STATUS.failed : OVERLAP_STATUS.passed,
      /**
       * Worst first, and that order is the numbering the enumerator sees: the report says
       * `#1 (34.0%), #2 (22.5%)`. GEO-008's map review must label its polygons from this same
       * array, or `#2` on screen and `#2` on the map are different plots.
       */
      conflicts: [...conflicts].sort((a, b) => b.rawPercent - a.rawPercent),
    };
  } catch {
    /**
     * A throwing index query, a missing table, or turf refusing a degenerate ring. None of them
     * mean "no overlap", so none of them may return a pass.
     */
    return unavailable(UNAVAILABLE_CAUSE.localFailure);
  }
};

/** `#1 (34.0%), #2 (22.5%)` — position in the worst-first array, which is the map's label too. */
const conflictList = (conflicts) =>
  conflicts.map((conflict, index) => `#${index + 1} (${conflict.percent}%)`).join(', ');

/**
 * The limit to print, which is not one number when accuracy varies between candidates.
 *
 * Each pair computes its own threshold from the accuracy and area of **both** polygons
 * (GEO-014 D-5), so two conflicts on one plot can legitimately be judged at 9.5 % and 20 %.
 * Printing only one of them would misstate why the other failed, so a mixed set prints a range.
 * The uniform case — neither polygon measured, everything falling back to the ceiling — is the
 * common one and still reads as a single number.
 */
const thresholdLabel = (conflicts) => {
  const values = [...new Set(conflicts.map((conflict) => conflict.threshold))].sort(
    (a, b) => a - b,
  );
  if (values.length === 1) {
    return `${values[0]}`;
  }
  return `${values[0]}-${values[values.length - 1]}`;
};

/**
 * Turn a check result into rule results, in the same shape the synchronous rules produce.
 *
 * **One result for all conflicts, not one per conflict.** Every overlap is still reported —
 * GEO-007 requires that — but as one numbered sentence rather than a stack of near-identical
 * lines. Device testing on 2026-09-23 showed why: the datapoint name is `generateDataPointName`
 * output, every meta answer joined with " - ", so a single failure filled six lines with an
 * administrative path and the enumerator still could not tell which plot was meant. Positions
 * carry that job now, and GEO-008's map will carry the identity.
 *
 * Severity resolves through the same helper and the same `required` clamp as every other rule
 * (D-9) — overlap is not special-cased.
 */
export const overlapResults = (checkResult, question = {}) => {
  const severity = resolveSeverity(
    { key: OVERLAP_RULE_KEY, configKey: OVERLAP_CONFIG_KEY },
    question,
  );
  if (checkResult?.status === OVERLAP_STATUS.unavailable) {
    return [
      {
        key: `${UNAVAILABLE_RULE_KEY}_${checkResult.cause}`,
        id: `${UNAVAILABLE_RULE_KEY}-${checkResult.cause}`,
        pass: false,
        skipped: false,
        severity,
        params: { cause: checkResult.cause },
      },
    ];
  }
  const conflicts = checkResult?.conflicts || [];
  if (!conflicts.length) {
    return [];
  }
  const single = conflicts.length === 1;
  return [
    {
      key: single ? OVERLAP_RULE_KEY : OVERLAP_MANY_RULE_KEY,
      id: OVERLAP_RULE_KEY,
      pass: false,
      skipped: false,
      severity,
      params: {
        count: conflicts.length,
        actual: conflicts[0].percent,
        list: conflictList(conflicts),
        threshold: thresholdLabel(conflicts),
      },
    },
  ];
};

/**
 * "Never validated" is a reachable state by design (D-1) and must not read as a pass. For a
 * required question it blocks submission exactly as a failure does; for an optional one it warns.
 */
export const notValidatedResult = (question = {}) => ({
  key: NOT_VALIDATED_RULE_KEY,
  id: NOT_VALIDATED_RULE_KEY,
  pass: false,
  skipped: false,
  severity: resolveSeverity({ key: OVERLAP_RULE_KEY, configKey: OVERLAP_CONFIG_KEY }, question),
  params: {},
});

/**
 * What the submit gate should treat as failing, given whatever the Validate button last stored.
 *
 * Absent or stale state is **not** a pass — it is the "never validated" state D-1 creates, and
 * closing it is what stops the button from becoming an opt-out from the whole feature.
 */
export const storedOverlapFailures = (stored, question = {}, points = null) => {
  const stale = points !== null && stored?.signature !== signatureOf(points);
  if (!stored || stale || stored.status === OVERLAP_STATUS.notValidated) {
    return [notValidatedResult(question)];
  }
  if (stored.status === OVERLAP_STATUS.checking) {
    return [notValidatedResult(question)];
  }
  if (stored.status === OVERLAP_STATUS.passed) {
    return [];
  }
  return stored.results || [];
};
