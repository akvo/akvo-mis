import sql from '../sql';
import crudUsers from './crud-users';

const formsQuery = () => ({
  selectLatestFormVersion: async (db, { user }) => {
    const latest = 1;
    const selectJoin = `SELECT
          f.id,
          f.userId,
          f.formId,
          f.version,
          f.name,
          f.json,
          -- Card title suffix: registration datapoints the backend has.
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1 AND dp.locallyCreated = 0
            THEN dp.id END
          ) AS registered,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1 AND dp.locallyCreated = 1
            THEN dp.id END
          ) + COALESCE((
            SELECT COUNT(DISTINCT mdp.id)
            FROM datapoints mdp
            INNER JOIN forms mf ON mdp.form = mf.id
            WHERE mf.parentId = f.formId
              AND mdp.user = ?
              AND mdp.locallyCreated = 1
              AND mdp.submitted = 1
          ), 0) AS submitted,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 0
            THEN dp.id END
          ) AS draft,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
              AND dp.locallyCreated = 0
              AND dp.syncedAt IS NOT NULL
            THEN dp.id END
          ) + COALESCE((
            SELECT COUNT(DISTINCT mdp.id)
            FROM datapoints mdp
            INNER JOIN forms mf ON mdp.form = mf.id
            WHERE mf.parentId = f.formId
              AND mdp.user = ?
              AND mdp.locallyCreated = 0
              AND mdp.submitted = 1
              AND mdp.syncedAt IS NOT NULL
          ), 0) AS synced
        FROM forms f
        LEFT JOIN datapoints dp ON f.id = dp.form AND dp.user = ?
        WHERE f.latest = ? AND f.parentId IS NULL
        GROUP BY f.id, f.formId, f.version, f.name, f.json;`;
    const rows = await sql.executeQuery(db, selectJoin, [user, user, user, latest]);
    return rows;
  },
  selectFormById: async (db, { id }) => {
    const rows = await sql.getFirstRow(db, 'forms', { id });
    return rows;
  },
  selectFormByIdAndVersion: async (db, { id: formId, version }) => {
    const rows = await sql.getFilteredRows(db, 'forms', { formId, version });
    return rows;
  },
  addForm: async (db, { userId, id: formId, parentId, version, formJSON }) => {
    const res = await sql.insertRow(db, 'forms', {
      formId,
      version,
      latest: 1,
      userId: userId || 0,
      parentId: parentId || null,
      name: formJSON?.name || null,
      json: formJSON ? JSON.stringify(formJSON).replace(/'/g, "''") : null,
      createdAt: new Date().toISOString(),
    });
    return res;
  },
  getMyForms: async (db) => {
    const session = await crudUsers.getActiveUser(db);
    const rows = await sql.getFilteredRows(db, 'forms', { userId: session.id });
    return rows;
  },
  deleteForm: async (db, id) => {
    const rowsAffected = await sql.deleteRow(db, 'forms', { id });
    return rowsAffected;
  },
  getByFormId: async (db, { formId }) => {
    const row = await sql.getFirstRow(db, 'forms', { formId });
    return row;
  },
  upsertForm: async (db, { userId, id: formId, parentId, version, formJSON }) => {
    const existing = await sql.getFirstRow(db, 'forms', { formId, userId: userId || 0 });
    if (existing) {
      await sql.updateRow(
        db,
        'forms',
        { id: existing.id },
        {
          version,
          latest: 1,
          parentId: parentId || null,
          name: formJSON?.name || null,
          json: formJSON ? JSON.stringify(formJSON).replace(/'/g, "''") : null,
        },
      );
      return existing.id;
    }
    return sql.insertRow(db, 'forms', {
      formId,
      version,
      latest: 1,
      userId: userId || 0,
      parentId: parentId || null,
      name: formJSON?.name || null,
      json: formJSON ? JSON.stringify(formJSON).replace(/'/g, "''") : null,
      createdAt: new Date().toISOString(),
    });
  },
  getFormOptions: async (db, { parentId, uuid }) => {
    const selectJoin = `SELECT
          f.id,
          f.parentId,
          f.userId,
          f.formId,
          f.version,
          f.name,
          f.json,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
            THEN dp.id END
          ) AS submitted,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 0
            AND dp.syncedAt IS NULL THEN dp.id END
          ) AS draft,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1 AND dp.syncedAt IS NOT NULL
            THEN dp.id END
          ) AS synced
        FROM forms f
        LEFT JOIN datapoints dp ON f.id = dp.form AND dp.uuid = ?
        WHERE f.parentId = ?
        GROUP BY f.id, f.formId, f.version, f.name, f.json;`;
    const rows = await sql.executeQuery(db, selectJoin, [uuid, parentId]);
    return rows;
  },
});

const crudForms = formsQuery();

export default crudForms;
