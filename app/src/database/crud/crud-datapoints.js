import sql from '../sql';

const selectDataPointById = async (db, { id }) => {
  const current = await sql.getFirstRow(db, 'datapoints', { id });
  if (!current) {
    return false;
  }
  return {
    ...current,
    json: JSON.parse(current.json.replace(/''/g, "'")),
  };
};

const dataPointsQuery = () => ({
  selectDataPointById,
  selectDataPointsByFormAndSubmitted: async (db, { form, submitted, user, uuid }) => {
    const uuidVal = uuid ? { uuid } : {};
    const userVal = user ? { user } : {};
    // Omitting `submitted` returns drafts and submissions together, so the list can
    // filter them client-side instead of re-querying on every checkbox toggle.
    const submittedVal = typeof submitted === 'number' ? { submitted } : {};
    const columns = { form, ...submittedVal, ...userVal, ...uuidVal };
    const rows = await sql.getFilteredRows(db, 'datapoints', { ...columns }, 'id', 'DESC', true);
    return rows;
  },
  selectSubmissionToSync: async (db, limit = null) => {
    const rows = await sql.executeQuery(
      db,
      `SELECT
          datapoints.*,
          forms.formId,
          forms.json AS json_form
        FROM datapoints
        JOIN forms ON datapoints.form = forms.id
        WHERE datapoints.syncedAt IS NULL
          AND (
            datapoints.submitted = 1
            -- A draft the server already knows about must keep syncing:
            -- onSyncDraftDatapoint dedups downloads by draftId, so holding it back
            -- locally would make the next download insert a duplicate.
            OR datapoints.draftId IS NOT NULL
            OR datapoints.sendToWeb = 1
          )
        ORDER BY datapoints.createdAt ASC
        ${limit ? `LIMIT ${parseInt(limit, 10)}` : ''}`,
    );
    return rows;
  },
  saveDataPoint: async (
    db,
    {
      uuid,
      form,
      user,
      name,
      geo,
      submitted,
      duration,
      json,
      repeats,
      syncedAt,
      administrationId,
      draftId,
      id,
      locallyCreated,
      submissionKey,
      sendToWeb,
    },
  ) => {
    try {
      const repeatsVal = repeats ? { repeats } : {};
      const submittedAt = submitted ? { submittedAt: new Date().toISOString() } : {};
      const geoVal = geo ? { geo } : {};
      const uuidVal = uuid ? { uuid } : {};
      const syncedAtVal = syncedAt ? { syncedAt } : {};
      const admVal = administrationId ? { administrationId } : {};
      const draftVal = draftId ? { draftId } : {};
      const idVal = id ? { id } : {};
      const locallyCreatedVal =
        locallyCreated !== undefined ? { locallyCreated: locallyCreated === 1 ? 1 : 0 } : {};
      const submissionKeyVal = submissionKey ? { submissionKey } : {};
      // Truthy-only, so an edit can never silently unset the flag.
      const sendToWebVal = sendToWeb ? { sendToWeb: 1 } : {};

      const dataToInsert = {
        form,
        user,
        name,
        submitted,
        duration: duration || 0,
        createdAt: new Date().toISOString(),
        json: json ? JSON.stringify(json).replace(/'/g, "''") : null,
        ...geoVal,
        ...submittedAt,
        ...repeatsVal,
        ...uuidVal,
        ...syncedAtVal,
        ...admVal,
        ...draftVal,
        ...idVal,
        ...locallyCreatedVal,
        ...submissionKeyVal,
        ...sendToWebVal,
      };

      const res = await sql.insertRow(db, 'datapoints', dataToInsert);
      return res;
    } catch (error) {
      throw new Error(`Error saving datapoint: ${error.message}`);
    }
  },
  updateDataPoint: async (
    db,
    {
      id,
      name,
      geo,
      submitted,
      duration,
      submittedAt,
      syncedAt,
      json,
      repeats,
      locallyCreated,
      submissionKey,
      sendToWeb,
    },
  ) => {
    try {
      const repeatsVal = repeats ? { repeats } : {};
      const submittedVal = submitted !== undefined ? { submitted } : {};
      const syncedAtVal = syncedAt !== undefined ? { syncedAt } : {};
      const locallyCreatedVal =
        locallyCreated !== undefined ? { locallyCreated: locallyCreated === 1 ? 1 : 0 } : {};
      const submissionKeyVal = submissionKey ? { submissionKey } : {};
      // Truthy-only: set-once semantics, matching setSendToWeb.
      const sendToWebVal = sendToWeb ? { sendToWeb: 1 } : {};

      const res = await sql.updateRow(
        db,
        'datapoints',
        { id },
        {
          name,
          geo,
          duration,
          syncedAt,
          submittedAt: submitted && !submittedAt ? new Date().toISOString() : submittedAt,
          json: json ? JSON.stringify(json).replace(/'/g, "''") : null,
          ...submittedVal,
          ...repeatsVal,
          ...syncedAtVal,
          ...locallyCreatedVal,
          ...submissionKeyVal,
          ...sendToWebVal,
        },
      );
      return res;
    } catch (error) {
      throw new Error(`Error updating datapoint: ${error.message}`);
    }
  },
  /**
   * Confirms an upload by stamping syncedAt. Writes only that one column —
   * passing a raw row through updateDataPoint would re-stringify its
   * already-serialised json. locallyCreated is an immutable origin flag and is
   * deliberately NOT touched: a device-created row stays locallyCreated = 1
   * after syncing, so "device data that reached the server" remains queryable.
   */
  markSynced: async (db, id, draftId = null) => {
    // draftId is the backend row id returned by /sync. Storing it right away
    // makes the next save of this draft sync as ?id=<draftId> (an update)
    // instead of creating a duplicate backend draft.
    const draftIdVal = draftId ? { draftId } : {};
    const res = await sql.updateRow(
      db,
      'datapoints',
      { id },
      {
        syncedAt: new Date().toISOString(),
        ...draftIdVal,
      },
    );
    return res;
  },
  saveAsPending: async (db, id) => {
    const res = await sql.updateRow(
      db,
      'datapoints',
      { id },
      {
        syncedAt: null,
      },
    );
    return res;
  },
  getDraftPendingSync: async (db) => {
    const rows = await sql.safeExecuteQuery(
      db,
      `SELECT * FROM datapoints WHERE submitted = ? AND draftId IS NULL AND syncedAt IS NOT NULL`,
      [0],
      'getDraftPendingSync',
    );
    return rows;
  },
  getByDraftId: async (db, { draftId }) => {
    const res = await sql.getFirstRow(db, 'datapoints', { draftId });
    if (!res) {
      return false;
    }
    return {
      ...res,
      json: res?.json ? JSON.parse(res.json.replace(/''/g, "'")) : null,
    };
  },
  deleteDraftIdIsNull: async (db) => {
    const res = await sql.safeExecuteQuery(
      db,
      'DELETE FROM datapoints WHERE submitted = ? AND draftId IS NULL AND syncedAt IS NOT NULL',
      [0],
      'deleteDraftIdIsNull',
    );
    return res;
  },
  deleteDraftSynced: async (db) => {
    const res = await sql.safeExecuteQuery(
      db,
      'DELETE FROM datapoints WHERE submitted = ? AND draftId IS NOT NULL AND syncedAt IS NOT NULL',
      [0],
      'deleteDraftSynced',
    );
    return res;
  },
  /**
   * Writes only the json column. Used to repair answers (e.g. retake a missing
   * photo) without touching syncedAt, so the row stays in the upload queue.
   */
  updateJson: async (db, id, json) => {
    const res = await sql.updateRow(
      db,
      'datapoints',
      { id },
      { json: JSON.stringify(json).replace(/'/g, "''") },
    );
    return res;
  },
  /**
   * Links a local draft to its backend row without stamping syncedAt, so the
   * local answers stay queued and the next upload updates the backend draft
   * in place instead of creating a duplicate.
   */
  linkDraftId: async (db, id, draftId) => {
    const res = await sql.updateRow(db, 'datapoints', { id }, { draftId });
    return res;
  },
  /**
   * Finds a local pending draft matching a backend draft by uuid. Drafts
   * uploaded by app versions before draftId bookkeeping existed can only be
   * matched this way, otherwise the draft download inserts a duplicate.
   */
  getDraftByUUID: async (db, { uuid, form }) => {
    const res = await sql.safeGetFirstRow(
      db,
      `SELECT * FROM datapoints
        WHERE uuid = ? AND form = ? AND submitted = ? AND draftId IS NULL`,
      [uuid, form, 0],
      'getDraftByUUID',
    );
    return res;
  },
  getByUUID: async (db, { uuid, form }) => {
    const formVal = form ? { form } : {};
    const res = await sql.getFirstRow(db, 'datapoints', { uuid, ...formVal });
    return res;
  },
  updateByUUID: async (db, { uuid, form, json, syncedAt, repeats }) => {
    if (!json || typeof json !== 'object') {
      return false;
    }
    const repeatsVal = repeats ? { repeats } : {};
    const formVal = form ? { form } : {};
    const res = await sql.updateRow(
      db,
      'datapoints',
      { uuid, ...formVal },
      {
        json: JSON.stringify(json).replace(/'/g, "''"),
        syncedAt: syncedAt || new Date().toISOString(),
        ...repeatsVal,
      },
    );
    return res;
  },
  totalSavedData: async (db, formDBId, uuid = null) => {
    try {
      if (uuid) {
        const res = await sql.safeGetFirstRow(
          db,
          'SELECT COUNT(*) AS total FROM datapoints WHERE submitted = ? AND form = ? AND uuid = ?',
          [0, formDBId, uuid],
          'totalSavedData with uuid',
        );
        return res?.total || 0;
      }
      const res = await sql.safeGetFirstRow(
        db,
        'SELECT COUNT(*) AS total FROM datapoints WHERE submitted = ? AND form = ?',
        [0, formDBId],
        'totalSavedData without uuid',
      );
      return res?.total || 0;
    } catch (error) {
      throw new Error(`Error in totalSavedData: ${error.message}`);
    }
  },
  /**
   * Local-only delete. The server copy, if any, is untouched — a draft with a
   * draftId re-downloads on the next sync, which the confirmation dialog warns about.
   */
  deleteDataPoint: async (db, id) => {
    await sql.deleteRow(db, 'datapoints', id);
    return true;
  },
  /**
   * Opt a local-born draft into web upload. Set once: updateDataPoint never writes
   * this column, so the flag survives every later edit of the draft.
   */
  setSendToWeb: async (db, id) => {
    const res = await sql.updateRow(db, 'datapoints', { id }, { sendToWeb: 1 });
    return res;
  },
  /**
   * How many OTHER datapoints still reference this file URI. Guards the local file
   * cleanup on delete: a shared file must outlive the row being deleted, or the
   * surviving row shows a broken preview.
   */
  countJsonReferences: async (db, uri, excludeId) => {
    const res = await sql.safeGetFirstRow(
      db,
      'SELECT COUNT(*) AS total FROM datapoints WHERE id != ? AND json LIKE ?',
      [excludeId, `%${uri}%`],
      'countJsonReferences',
    );
    return res?.total || 0;
  },
  /**
   * Per-registration monitoring rollup for the datapoint list. One query per list
   * load, grouped by the registration uuid that monitoring datapoints inherit.
   * parentFormId is the registration form's BACKEND formId, so every monitoring form
   * version is covered. Registration rows never appear: their forms have parentId NULL.
   */
  getMonitoringStats: async (db, parentFormId, user) => {
    const rows = await sql.safeExecuteQuery(
      db,
      `SELECT dp.uuid,
          SUM(CASE WHEN dp.submitted = 0 THEN 1 ELSE 0 END) AS draftCount,
          SUM(CASE WHEN dp.submitted = 1 THEN 1 ELSE 0 END) AS submissionCount,
          MAX(CASE WHEN dp.submitted = 1 THEN dp.submittedAt END) AS lastSubmissionAt
        FROM datapoints dp
        JOIN forms f ON dp.form = f.id
        WHERE f.parentId = ? AND dp.user = ? AND dp.uuid IS NOT NULL
        GROUP BY dp.uuid`,
      [parentFormId, user],
      'getMonitoringStats',
    );
    return rows;
  },
  /**
   * Every unfinished draft in one form family — the registration form plus all of its
   * monitoring forms, across versions. Backs the grouped drafts-only view. The form's
   * json is deliberately excluded: it is large and only needed for the one row the
   * user opens, which crudForms.selectFormById fetches on tap.
   */
  getFamilyDrafts: async (db, { formDbId, backendFormId, user }) => {
    const rows = await sql.safeExecuteQuery(
      db,
      `SELECT dp.*, f.formId AS groupFormId, f.name AS groupName, f.parentId AS groupParentId
        FROM datapoints dp
        JOIN forms f ON dp.form = f.id
        WHERE dp.submitted = 0 AND dp.user = ?
          AND (f.id = ? OR f.parentId = ?)
        ORDER BY f.parentId IS NULL DESC, f.name ASC, dp.createdAt DESC`,
      [user, formDbId, backendFormId],
      'getFamilyDrafts',
    );
    return rows;
  },
  /**
   * Total unfinished drafts in one form family. Same scope as getFamilyDrafts, but
   * independent of whichever list query is currently loaded — the checkbox label has
   * to show the family total even while the list is showing submissions only.
   */
  countFamilyDrafts: async (db, { formDbId, backendFormId, user }) => {
    const res = await sql.safeGetFirstRow(
      db,
      `SELECT COUNT(*) AS total
        FROM datapoints dp
        JOIN forms f ON dp.form = f.id
        WHERE dp.submitted = 0 AND dp.user = ?
          AND (f.id = ? OR f.parentId = ?)`,
      [user, formDbId, backendFormId],
      'countFamilyDrafts',
    );
    return res?.total || 0;
  },
  countSyncedByFormId: async (db, backendFormId) => {
    const res = await sql.safeGetFirstRow(
      db,
      `SELECT COUNT(*) AS total FROM datapoints dp
       INNER JOIN forms f ON dp.form = f.id
       WHERE f.formId = ? AND dp.syncedAt IS NOT NULL`,
      [backendFormId],
      'countSyncedByFormId',
    );
    return res?.total || 0;
  },
});

const crudDataPoints = dataPointsQuery();

export default crudDataPoints;
