/**
 * Real-SQL tests for the Home form-count queries (APP-585). These run the ACTUAL SQL against
 * an in-memory SQLite (better-sqlite3), not a mocked result, so they catch JOIN/matching bugs
 * in the counting logic — which is exactly where the parent/child/version mixups lived.
 *
 * Invariants under test:
 *  - Parent card counts are PARENT-ONLY (monitoring rows are never rolled in) — D-5.
 *  - The collapsed header aggregate (subDraft/subPending/subSynced) EQUALS the sum of the
 *    per-sub-form cards (selectSubFormsByParent) — no "header says 2, cards show 1".
 *  - A monitoring datapoint saved under an earlier form VERSION still counts on its child's
 *    latest card (cross-version by formId).
 *  - Draft counts every unsubmitted row (incl. downloaded); pending/synced require locallyCreated.
 *  - countPendingSync is device-wide (parent + monitoring).
 */
import Database from 'better-sqlite3';
import crudForms from '../crud-forms';
import crudDataPoints from '../crud-datapoints';

const makeDb = () => {
  const raw = new Database(':memory:');
  raw.exec(`
    CREATE TABLE forms (
      id INTEGER PRIMARY KEY, formId INTEGER, parentId INTEGER,
      version TEXT, name TEXT, json TEXT, latest INTEGER, userId INTEGER
    );
    CREATE TABLE datapoints (
      id INTEGER PRIMARY KEY, form INTEGER, user INTEGER,
      submitted INTEGER, syncedAt TEXT, locallyCreated INTEGER
    );
  `);
  return {
    raw,
    execAsync: async (s) => raw.exec(s),
    runAsync: async (s, ...p) => raw.prepare(s).run(...p),
    getAllAsync: async (s, ...p) => raw.prepare(s).all(...p),
    getFirstAsync: async (s, ...p) => raw.prepare(s).get(...p),
  };
};

let db;
let formId = 0;
let dpId = 0;

const addForm = ({ formId: fId, parentId = null, latest = 1, user = 1, name = 'Form', version = '1' }) => {
  formId += 1;
  db.raw
    .prepare(
      'INSERT INTO forms (id, formId, parentId, version, name, json, latest, userId) VALUES (?,?,?,?,?,?,?,?)',
    )
    .run(formId, fId, parentId, version, name, '{}', latest, user);
  return formId;
};

// state: 'draft' | 'pending' | 'synced' | 'downloadedDraft' | 'downloadedSynced'
const addPoints = (form, user, state, n = 1) => {
  const map = {
    draft: { submitted: 0, syncedAt: null, locallyCreated: 1 },
    pending: { submitted: 1, syncedAt: null, locallyCreated: 1 },
    synced: { submitted: 1, syncedAt: '2026-01-01T00:00:00Z', locallyCreated: 1 },
    downloadedDraft: { submitted: 0, syncedAt: null, locallyCreated: 0 },
    downloadedSynced: { submitted: 1, syncedAt: '2026-01-01T00:00:00Z', locallyCreated: 0 },
  };
  const s = map[state];
  Array.from({ length: n }).forEach(() => {
    dpId += 1;
    db.raw
      .prepare(
        'INSERT INTO datapoints (id, form, user, submitted, syncedAt, locallyCreated) VALUES (?,?,?,?,?,?)',
      )
      .run(dpId, form, user, s.submitted, s.syncedAt, s.locallyCreated);
  });
};

beforeEach(() => {
  db = makeDb();
  formId = 0;
  dpId = 0;
});

describe('selectLatestFormVersion — parent-only counts (D-5)', () => {
  it('does NOT roll monitoring rows into the parent tiles', async () => {
    const parent = addForm({ formId: 100, name: 'Pump Station' }); // local id 1
    const child = addForm({ formId: 200, parentId: 100, name: 'Monitoring' }); // local id 2
    // Parent registrations: 2 synced, 1 pending, 1 draft.
    addPoints(parent, 1, 'synced', 2);
    addPoints(parent, 1, 'pending', 1);
    addPoints(parent, 1, 'draft', 1);
    // Child monitoring: 1 synced, 1 draft.
    addPoints(child, 1, 'synced', 1);
    addPoints(child, 1, 'draft', 1);

    const [row] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    // Parent-only: draft is 1 (its own), NOT 2 (would be the mixed total).
    expect(row.draft).toBe(1);
    expect(row.submitted).toBe(1); // pending
    expect(row.synced).toBe(2);
    expect(row.registered).toBe(2); // synced registrations held by the backend
    expect(row.subFormCount).toBe(1);
    // Monitoring totals live in their own columns.
    expect(row.subDraft).toBe(1);
    expect(row.subPending).toBe(0);
    expect(row.subSynced).toBe(1);
  });

  it('subFormCount is 0 and sub totals are 0 when there are no children', async () => {
    const parent = addForm({ formId: 100 });
    addPoints(parent, 1, 'synced', 3);
    const [row] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    expect(row.subFormCount).toBe(0);
    expect(row.subDraft + row.subPending + row.subSynced).toBe(0);
  });

  it('only returns parent (parentId IS NULL) rows', async () => {
    addForm({ formId: 100 });
    addForm({ formId: 200, parentId: 100 });
    const rows = await crudForms.selectLatestFormVersion(db, { user: 1 });
    expect(rows).toHaveLength(1);
    expect(rows[0].formId).toBe(100);
  });
});

describe('header aggregate == sum of sub-form cards (the 2-vs-1 bug)', () => {
  it('reconciles across two children', async () => {
    addForm({ formId: 100 });
    const monitoring = addForm({ formId: 200, parentId: 100, name: 'Monitoring' });
    const quick = addForm({ formId: 300, parentId: 100, name: 'Quick Monitoring' });
    addPoints(monitoring, 1, 'draft', 1);
    addPoints(quick, 1, 'synced', 2);

    const [parentRow] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    const subs = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });

    const sum = subs.reduce(
      (a, s) => ({ draft: a.draft + s.draft, pending: a.pending + s.submitted, synced: a.synced + s.synced }),
      { draft: 0, pending: 0, synced: 0 },
    );
    expect(sum).toEqual({ draft: 1, pending: 0, synced: 2 });
    // Header chips must match the cards exactly.
    expect(parentRow.subDraft).toBe(sum.draft);
    expect(parentRow.subPending).toBe(sum.pending);
    expect(parentRow.subSynced).toBe(sum.synced);
  });

  it('counts a monitoring datapoint saved under an OLDER child version on the latest card', async () => {
    addForm({ formId: 100 });
    const childOld = addForm({ formId: 200, parentId: 100, latest: 0, version: '1' }); // id 2
    addForm({ formId: 200, parentId: 100, latest: 1, version: '2' }); // id 3 (latest)
    addPoints(childOld, 1, 'synced', 2); // saved against the OLD version row

    const subs = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });
    const [parentRow] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    expect(subs).toHaveLength(1); // one child (latest), not two
    expect(subs[0].synced).toBe(2); // old-version datapoints attributed to the latest card
    expect(parentRow.subSynced).toBe(2);
  });

  it('excludes orphan datapoints (child form with no latest row) from BOTH', async () => {
    addForm({ formId: 100 });
    const liveChild = addForm({ formId: 200, parentId: 100, latest: 1 });
    const orphan = addForm({ formId: 999, parentId: 100, latest: 0 }); // no latest=1 row
    addPoints(liveChild, 1, 'synced', 1);
    addPoints(orphan, 1, 'synced', 1); // belongs to a form that has no card

    const subs = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });
    const [parentRow] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    const cardSynced = subs.reduce((a, s) => a + s.synced, 0);
    expect(cardSynced).toBe(1);
    expect(parentRow.subSynced).toBe(1); // header matches cards — no phantom +1
  });
});

describe('selectSubFormsByParent — per-child semantics', () => {
  it('draft counts downloaded rows; pending/synced require locallyCreated', async () => {
    addForm({ formId: 100 });
    const child = addForm({ formId: 200, parentId: 100 });
    addPoints(child, 1, 'draft', 1);
    addPoints(child, 1, 'downloadedDraft', 1); // locallyCreated 0, still a draft
    addPoints(child, 1, 'downloadedSynced', 1); // locallyCreated 0 — NOT counted as synced
    addPoints(child, 1, 'synced', 1);

    const [row] = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });
    expect(row.draft).toBe(2); // both drafts
    expect(row.synced).toBe(1); // only the locally-created synced one
    expect(row.submitted).toBe(0);
  });

  it('scopes to the given user', async () => {
    addForm({ formId: 100 });
    const child = addForm({ formId: 200, parentId: 100 });
    addPoints(child, 1, 'synced', 1);
    addPoints(child, 2, 'synced', 1); // other user
    const [row] = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });
    expect(row.synced).toBe(1);
  });

  it('returns [] when the parent has no children', async () => {
    addForm({ formId: 100 });
    const subs = await crudForms.selectSubFormsByParent(db, { parentFormId: 100, user: 1 });
    expect(subs).toHaveLength(0);
  });
});

describe('countPendingSync — device-wide', () => {
  it('counts parent AND monitoring pending rows for the user', async () => {
    const parent = addForm({ formId: 100 });
    const child = addForm({ formId: 200, parentId: 100 });
    addPoints(parent, 1, 'pending', 1);
    addPoints(child, 1, 'pending', 1);
    addPoints(parent, 1, 'synced', 1); // not pending
    addPoints(child, 1, 'downloadedSynced', 1); // not pending
    addPoints(parent, 2, 'pending', 1); // other user
    const pending = await crudDataPoints.countPendingSync(db, { user: 1 });
    expect(pending).toBe(2);
  });

  it('is 0 when nothing is waiting', async () => {
    const parent = addForm({ formId: 100 });
    addPoints(parent, 1, 'synced', 2);
    expect(await crudDataPoints.countPendingSync(db, { user: 1 })).toBe(0);
  });
});
