import sql from '../sql';
import crudUsers from './crud-users';

const formsQuery = () => ({
  selectLatestFormVersion: async (db, { user }) => {
    const latest = 1;
    // Parent-only counts (APP-585 D-5): monitoring/child datapoints are NOT rolled into
    // the parent card. The card expander lists each sub-form's own counts separately
    // (selectSubFormsByParent), so a registration with 2 own + 2 monitoring reads "2", not 4.
    const selectJoin = `SELECT
          f.id,
          f.userId,
          f.formId,
          f.version,
          f.name,
          f.json,
          -- Card title suffix: registration datapoints the backend holds,
          -- whoever made them (downloaded + this device's synced submissions).
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1 AND dp.syncedAt IS NOT NULL
            THEN dp.id END
          ) AS registered,
          -- "Pending sync": this device's submissions still waiting to upload.
          -- Drains as syncedAt fills in; the origin flag stays 1 (APP-255 D-17).
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
              AND dp.locallyCreated = 1
              AND dp.syncedAt IS NULL
            THEN dp.id END
          ) AS submitted,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 0
            THEN dp.id END
          ) AS draft,
          -- "Synced": this device's submissions that reached the server.
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
              AND dp.locallyCreated = 1
              AND dp.syncedAt IS NOT NULL
            THEN dp.id END
          ) AS synced,
          -- Whether to show the card's sub-form expander: a count of child FORMS
          -- (not datapoints), so it never mixes with the counts above.
          (
            SELECT COUNT(*) FROM forms cf
            WHERE cf.parentId = f.formId AND cf.latest = 1
          ) AS subFormCount,
          -- Monitoring (child) totals, kept SEPARATE from the parent counts so the
          -- expander header can show them while collapsed (APP-585). Not summed in.
          -- Scoped to the LATEST children under this parent, across all their versions —
          -- the SAME rule selectSubFormsByParent uses per card — so this header equals the
          -- sum of the sub-form cards. A datapoint on a form that is not a current child
          -- (orphan/replaced) is excluded here too, since no card could show it.
          COALESCE((
            SELECT COUNT(DISTINCT mdp.id)
            FROM forms cf
            JOIN forms cfv ON cfv.formId = cf.formId
            JOIN datapoints mdp ON mdp.form = cfv.id
            WHERE cf.parentId = f.formId AND cf.latest = 1
              AND mdp.user = ? AND mdp.submitted = 0
          ), 0) AS subDraft,
          COALESCE((
            SELECT COUNT(DISTINCT mdp.id)
            FROM forms cf
            JOIN forms cfv ON cfv.formId = cf.formId
            JOIN datapoints mdp ON mdp.form = cfv.id
            WHERE cf.parentId = f.formId AND cf.latest = 1
              AND mdp.user = ? AND mdp.locallyCreated = 1 AND mdp.submitted = 1 AND mdp.syncedAt IS NULL
          ), 0) AS subPending,
          COALESCE((
            SELECT COUNT(DISTINCT mdp.id)
            FROM forms cf
            JOIN forms cfv ON cfv.formId = cf.formId
            JOIN datapoints mdp ON mdp.form = cfv.id
            WHERE cf.parentId = f.formId AND cf.latest = 1
              AND mdp.user = ? AND mdp.locallyCreated = 1 AND mdp.submitted = 1 AND mdp.syncedAt IS NOT NULL
          ), 0) AS subSynced
        FROM forms f
        LEFT JOIN datapoints dp ON f.id = dp.form AND dp.user = ?
        WHERE f.latest = ? AND f.parentId IS NULL
        GROUP BY f.id, f.formId, f.version, f.name, f.json;`;
    // Five ? binds, in SQL order: subDraft / subPending / subSynced subqueries (user),
    // the LEFT JOIN dp.user, and f.latest.
    const rows = await sql.executeQuery(db, selectJoin, [user, user, user, user, latest]);
    return rows;
  },
  // Each sub-form of a parent registration, with its OWN draft/pending/synced counts,
  // for the Home card expander (APP-585). Same shape as a parent row (incl. parentId +
  // json) so tapping a sub-form card opens Submission exactly like a parent card.
  selectSubFormsByParent: async (db, { parentFormId, user }) => {
    const selectJoin = `SELECT
          f.id,
          f.parentId,
          f.userId,
          f.formId,
          f.version,
          f.name,
          f.json,
          COUNT(DISTINCT CASE WHEN dp.submitted = 0 THEN dp.id END) AS draft,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
              AND dp.locallyCreated = 1
              AND dp.syncedAt IS NULL
            THEN dp.id END
          ) AS submitted,
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 1
              AND dp.locallyCreated = 1
              AND dp.syncedAt IS NOT NULL
            THEN dp.id END
          ) AS synced
        FROM forms f
        -- Count datapoints across ALL versions of each child form (match by formId), so a
        -- monitoring row saved under an earlier form version still shows on its card and
        -- agrees with the parent header aggregate, which is version-agnostic (APP-585).
        LEFT JOIN forms v ON v.formId = f.formId
        LEFT JOIN datapoints dp ON dp.form = v.id AND dp.user = ?
        WHERE f.parentId = ? AND f.latest = 1
        GROUP BY f.id, f.formId, f.version, f.name, f.json;`;
    const rows = await sql.executeQuery(db, selectJoin, [user, parentFormId]);
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
          -- Every unfinished draft, synced or not: a draft downloaded from the web
          -- is still one the user can open and finish. Counting only unsynced ones
          -- made this disagree with the Home card and the datapoint list.
          COUNT(
            DISTINCT CASE WHEN dp.submitted = 0
            THEN dp.id END
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
