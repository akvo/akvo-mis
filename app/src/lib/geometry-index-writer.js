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
export const finishDatapointSync = async (db, { markSyncComplete, clearQueue }) => {
  await markSyncComplete();
  await clearQueue(db);
  await crudConfig.updateConfig(db, { geometryIndexReady: 1 });
};
