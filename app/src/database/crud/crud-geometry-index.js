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
  replaceForDatapoint: async (db, { uuid, formId, rows }) => {
    await sql.safeExecuteQuery(
      db,
      `DELETE FROM ${tableName} WHERE uuid = ? AND formId = ?`,
      [uuid, formId],
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
      exclude = ' AND uuid != ?';
      params.push(excludeUuid);
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
