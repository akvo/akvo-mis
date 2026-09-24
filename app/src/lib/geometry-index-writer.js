import { crudConfig, crudGeometryIndex } from '../database/crud';
import { geoshapeAnswersFromJson, rowFromCoordinates, rowFromListGeometry } from './geometry-index';

/**
 * Write index rows from a GEO-005 list `geometry[]` payload (sync path).
 * Must run inside the same transaction as the datapoint write (GEO-006 D-6).
 */
export const writeIndexFromListGeometry = async (
  db,
  { uuid, formId, datapointId, name, geometry, isComplete },
) => {
  if (!Array.isArray(geometry) || !geometry.length) {
    await crudGeometryIndex.replaceForDatapoint(db, { uuid, formId, rows: [] });
    return;
  }
  const rows = geometry
    .map((entry) => rowFromListGeometry(entry, { datapointId, name, isComplete }))
    .filter((row) => row.questionId != null && Number.isFinite(row.minLat));
  await crudGeometryIndex.replaceForDatapoint(db, { uuid, formId, rows });
};

/**
 * Flip every row of a form to complete, once the form's last page has landed.
 *
 * This used to run inside `writeIndexFromListGeometry`, where `isComplete` is true for every
 * item on the final page — so a 100-row last page issued 100 full `UPDATE ... WHERE formId = ?`
 * sweeps over what can be 5,000 rows, each in its own datapoint transaction. The rows written
 * on that page already carry the right value; the sweep exists only to flip the EARLIER pages,
 * so it belongs once per form, at the end.
 */
export const markFormGeometryComplete = async (db, formId) => {
  await crudGeometryIndex.markFormComplete(db, formId);
};

/**
 * Write index rows from local answers (create / edit path).
 * Computes bbox + accuracy summary on device (GEO-006 acceptance criteria).
 *
 * No-ops when the form has no overlap-enabled geoshape — forms without one
 * do no indexing work.
 */
export const writeIndexFromAnswers = async (
  db,
  { uuid, formId, datapointId, name, answers, formJson, isComplete = true },
) => {
  const geoshapes = geoshapeAnswersFromJson(formJson, answers);
  if (!geoshapes.length) {
    // Still clear stale rows if a previously indexed polygon was removed,
    // but only when the form *could* have had one.
    const couldIndex = (formJson?.question_group || []).some((g) =>
      (g.question || []).some((q) => q?.extra?.geoConfig?.detectOverlaps === true),
    );
    if (couldIndex) {
      await crudGeometryIndex.replaceForDatapoint(db, { uuid, formId, rows: [] });
    }
    return;
  }
  const rows = geoshapes
    .map((g) =>
      rowFromCoordinates(g.coordinates, {
        datapointId,
        questionId: g.questionId,
        repeatIndex: g.repeatIndex,
        name,
        isComplete,
      }),
    )
    .filter(Boolean);
  await crudGeometryIndex.replaceForDatapoint(db, { uuid, formId, rows });
};

/**
 * Single place that marks a full datapoint sync finished (GEO-006 §10).
 * Called from both SyncService and the background task instead of
 * `markSyncComplete` directly.
 *
 * Order matters: the readiness flag must not flip if the backend cursor
 * update fails — otherwise GEO-007 would validate against a partial set
 * while the next sync still thinks nothing finished.
 */
export const finishDatapointSync = async (db, { markSyncComplete, clearQueue, full = false }) => {
  await markSyncComplete();
  await clearQueue(db);
  if (full) {
    await crudConfig.updateConfig(db, { geometryIndexReady: 1 });
  }
};

/**
 * Does the index still owe a full geometry pull?
 *
 * Readiness means "a full pull has landed since the migration or the last reset" — not "a sync
 * finished". The distinction is the whole gate: `/datapoint-list` is cursor-based, so an
 * upgraded device that synced yesterday receives **nothing**, the sync completes instantly, and
 * a flag set on that would declare an EMPTY post-migration index trustworthy. That is precisely
 * the state GEO-006 D-4 exists to refuse. So a sync run asks this first and, when it is true,
 * requests `geometry_full=true` for every form and only then may flip readiness.
 */
export const geometryIndexNeedsFullPull = async (db) => {
  const config = await crudConfig.getConfig(db);
  return config?.geometryIndexReady !== 1;
};

/**
 * The server's absolute geoshape count per form, kept across the queue being cleared.
 *
 * Stored as a JSON map on the config row because the sync queue — the obvious home — is wiped
 * the moment a sync finishes, which is exactly when validation needs the number.
 */
export const recordGeometryTotal = async (db, formId, total) => {
  if (!Number.isFinite(total)) {
    return;
  }
  const config = await crudConfig.getConfig(db);
  let totals = {};
  try {
    totals = JSON.parse(config?.geometryTotals || '{}') || {};
  } catch {
    totals = {};
  }
  if (totals[`${formId}`] === total) {
    return;
  }
  await crudConfig.updateConfig(db, {
    geometryTotals: JSON.stringify({ ...totals, [`${formId}`]: total }),
  });
};

export const readGeometryTotals = async (db) => {
  const config = await crudConfig.getConfig(db);
  try {
    return JSON.parse(config?.geometryTotals || '{}') || {};
  } catch {
    return {};
  }
};
