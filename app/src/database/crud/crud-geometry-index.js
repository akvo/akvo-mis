import sql from '../sql';

const tableName = 'geometry_index';

/**
 * Local spatial index for overlap candidates (GEO-006).
 *
 * Identity of a row is (uuid, formId, questionId, repeatIndex). Replaces by
 * that key; a datapoint rewrite deletes all of its rows then re-inserts.
 */
const geometryIndexQuery = () => ({
  /**
   * Drop every index row for a datapoint, then insert the supplied ones.
   * Empty `rows` clears the index for that datapoint (e.g. all polygons removed).
   */
  replaceForDatapoint: async (db, { uuid, formId, rows, datapointId = null }) => {
    /**
     * `datapointId`, when given, also sweeps that datapoint's rows filed under any other uuid —
     * the orphans a reopened draft left behind while FormPage minted a random uuid per session.
     * `datapointId = NULL` never matches, so callers without one delete by uuid exactly as before.
     */
    await sql.safeExecuteQuery(
      db,
      `DELETE FROM ${tableName} WHERE formId = ? AND (uuid = ? OR datapointId = ?)`,
      [formId, uuid, datapointId],
      'geometryIndex.replaceForDatapoint.delete',
    );
    if (!rows?.length) {
      return;
    }
    const createdAt = new Date().toISOString();
    await rows.reduce(async (prev, row) => {
      await prev;
      await sql.insertRow(db, tableName, {
        uuid,
        formId,
        datapointId: row.datapointId ?? null,
        questionId: row.questionId,
        repeatIndex: row.repeatIndex ?? 0,
        name: row.name ?? null,
        minLat: row.minLat,
        maxLat: row.maxLat,
        minLon: row.minLon,
        maxLon: row.maxLon,
        accuracyMax: row.accuracyMax ?? null,
        accuracyMeasured: row.accuracyMeasured ? 1 : 0,
        isComplete: row.isComplete ? 1 : 0,
        createdAt,
      });
    }, Promise.resolve());
  },

  /** GEO-005 last-page completeness: flip every row for the form. */
  markFormComplete: async (db, formId) => {
    await sql.safeExecuteQuery(
      db,
      `UPDATE ${tableName} SET isComplete = 1 WHERE formId = ?`,
      [formId],
      'geometryIndex.markFormComplete',
    );
  },

  /**
   * Indexed geoshape answers for a form — the number `geometry_total` is compared against.
   *
   * Rows, not datapoints: one datapoint can hold several geoshape answers, and a single missing
   * one is exactly the gap a datapoint-level count cannot see.
   */
  countByForm: async (db, formId) => {
    const res = await sql.safeGetFirstRow(
      db,
      `SELECT COUNT(*) AS total FROM ${tableName} WHERE formId = ?`,
      [formId],
      'geometryIndex.countByForm',
    );
    return res?.total || 0;
  },

  selectByUuid: async (db, { uuid, formId }) => {
    const formClause = formId ? ' AND formId = ?' : '';
    const params = formId ? [uuid, formId] : [uuid];
    return sql.safeExecuteQuery(
      db,
      `SELECT * FROM ${tableName} WHERE uuid = ?${formClause} ORDER BY questionId, repeatIndex`,
      params,
      'geometryIndex.selectByUuid',
    );
  },

  /**
   * Bbox range query used by GEO-007. Four single-column indexes; SQLite
   * picks the most selective (GEO-006 D-1).
   */
  findOverlapCandidates: async (
    db,
    { formId, questionId, minLat, maxLat, minLon, maxLon, excludeUuid },
  ) => {
    const params = [formId, questionId, maxLat, minLat, maxLon, minLon];
    let exclude = '';
    if (excludeUuid) {
      /**
       * By the row's uuid AND by the datapoint it points at. Before FormPage adopted a saved
       * datapoint's uuid, each save of a reopened draft wrote index rows under a random uuid; those
       * rows still name the draft's `datapointId`, so matching on uuid alone lets a plot overlap
       * itself through them.
       */
      exclude =
        ' AND uuid != ? AND (datapointId IS NULL OR datapointId NOT IN (SELECT id FROM datapoints WHERE uuid = ?))';
      params.push(excludeUuid, excludeUuid);
    }
    return sql.safeExecuteQuery(
      db,
      `SELECT * FROM ${tableName}
        WHERE formId = ?
          AND questionId = ?
          AND minLat <= ?
          AND maxLat >= ?
          AND minLon <= ?
          AND maxLon >= ?
          ${exclude}`,
      params,
      'geometryIndex.findOverlapCandidates',
    );
  },
});

const crudGeometryIndex = geometryIndexQuery();

export default crudGeometryIndex;
