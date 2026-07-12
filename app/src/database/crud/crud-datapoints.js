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
    const columns = { form, submitted, ...userVal, ...uuidVal };
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
    },
  ) => {
    try {
      const repeatsVal = repeats ? { repeats } : {};
      const submittedVal = submitted !== undefined ? { submitted } : {};
      const syncedAtVal = syncedAt !== undefined ? { syncedAt } : {};
      const locallyCreatedVal =
        locallyCreated !== undefined ? { locallyCreated: locallyCreated === 1 ? 1 : 0 } : {};
      const submissionKeyVal = submissionKey ? { submissionKey } : {};

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
