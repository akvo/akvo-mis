/**
 * Real-SQL tests (better-sqlite3 in-memory). crud takes `db` first and uses the async API;
 * these seed real rows and assert behaviour. Count aggregates live in crud-forms-counts.test.js.
 */
import crudDataPoints from '../crud-datapoints';
import { makeInMemoryDb, createCrudSchema } from '../../test-helpers/in-memory-db';

let db;

const insertForm = (id, formId) =>
  db.raw
    .prepare('INSERT INTO forms (id, formId, latest, userId) VALUES (?,?,1,1)')
    .run(id, formId);

beforeEach(() => {
  db = makeInMemoryDb();
  createCrudSchema(db);
});

describe('selectDataPointById', () => {
  it('returns false for a missing id', async () => {
    const result = await crudDataPoints.selectDataPointById(db, { id: 1 });
    expect(result).toBe(false);
  });

  it('returns the datapoint with parsed json for a valid id', async () => {
    const id = await crudDataPoints.saveDataPoint(db, {
      form: 123,
      user: 1,
      name: 'DP 1',
      submitted: 1,
      duration: 2.5,
      json: [{ 101: 'Answer 1' }],
    });
    const result = await crudDataPoints.selectDataPointById(db, { id });
    expect(result.name).toBe('DP 1');
    expect(result.form).toBe(123);
    expect(result.json).toEqual([{ 101: 'Answer 1' }]);
  });
});

describe('saveDataPoint', () => {
  it('inserts a row and returns its new id', async () => {
    const id = await crudDataPoints.saveDataPoint(db, {
      form: 123,
      user: 1,
      name: 'DP',
      submitted: 0,
      duration: 1,
      json: [{ 101: 'x' }],
    });
    expect(id).toBeGreaterThan(0);
    const row = db.raw.prepare('SELECT * FROM datapoints WHERE id = ?').get(id);
    expect(row.form).toBe(123);
    expect(row.submitted).toBe(0);
  });
});

describe('updateDataPoint', () => {
  it('stamps syncedAt on an existing row', async () => {
    const id = await crudDataPoints.saveDataPoint(db, {
      form: 123,
      user: 1,
      name: 'DP',
      submitted: 1,
      duration: 1,
      json: [{ 101: 'x' }],
    });
    const when = '2026-02-02T00:00:00Z';
    await crudDataPoints.updateDataPoint(db, {
      id,
      name: 'DP',
      submitted: 1,
      duration: 1,
      syncedAt: when,
      json: [{ 101: 'x' }],
    });
    const row = db.raw.prepare('SELECT syncedAt FROM datapoints WHERE id = ?').get(id);
    expect(row.syncedAt).toBe(when);
  });
});

describe('selectDataPointsByFormAndSubmitted', () => {
  beforeEach(async () => {
    // form 123: two submitted (user 1), one draft (user 1), one draft (user 2)
    await crudDataPoints.saveDataPoint(db, { form: 123, user: 1, name: 'a', submitted: 1, duration: 1, json: [{}] });
    await crudDataPoints.saveDataPoint(db, { form: 123, user: 1, name: 'b', submitted: 1, duration: 1, json: [{}] });
    await crudDataPoints.saveDataPoint(db, { form: 123, user: 1, name: 'c', submitted: 0, duration: 1, json: [{}] });
    await crudDataPoints.saveDataPoint(db, { form: 123, user: 2, name: 'd', submitted: 0, duration: 1, json: [{}] });
  });

  it('returns submitted rows for the form', async () => {
    const rows = await crudDataPoints.selectDataPointsByFormAndSubmitted(db, { form: 123, submitted: 1 });
    expect(rows).toHaveLength(2);
    expect(rows.every((r) => r.submitted === 1)).toBe(true);
  });

  it('returns draft rows for the form', async () => {
    const rows = await crudDataPoints.selectDataPointsByFormAndSubmitted(db, { form: 123, submitted: 0 });
    expect(rows).toHaveLength(2);
  });

  it('filters by user id', async () => {
    const rows = await crudDataPoints.selectDataPointsByFormAndSubmitted(db, { form: 123, submitted: 0, user: 2 });
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('d');
  });
});

describe('selectSubmissionToSync', () => {
  it('returns submitted rows with syncedAt NULL, joined to their form', async () => {
    insertForm(1, 123);
    db.raw
      .prepare('INSERT INTO datapoints (id, form, user, submitted, syncedAt, locallyCreated, createdAt) VALUES (?,?,?,?,?,?,?)')
      .run(1, 1, 1, 1, null, 1, '2026-01-01'); // pending
    db.raw
      .prepare('INSERT INTO datapoints (id, form, user, submitted, syncedAt, locallyCreated, createdAt) VALUES (?,?,?,?,?,?,?)')
      .run(2, 1, 1, 1, '2026-01-02', 1, '2026-01-02'); // already synced
    db.raw
      .prepare('INSERT INTO datapoints (id, form, user, submitted, syncedAt, locallyCreated, createdAt) VALUES (?,?,?,?,?,?,?)')
      .run(3, 1, 1, 0, null, 1, '2026-01-03'); // draft
    const rows = await crudDataPoints.selectSubmissionToSync(db);
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe(1);
    expect(rows[0].formId).toBe(123); // JOINed column
  });

  it('returns [] when nothing is waiting', async () => {
    const rows = await crudDataPoints.selectSubmissionToSync(db);
    expect(rows).toEqual([]);
  });
});

describe('family status queries (APP-596)', () => {
  const addFamForm = (id, formId, parentId, name) =>
    db.raw
      .prepare('INSERT INTO forms (id, formId, parentId, name, latest, userId) VALUES (?,?,?,?,1,1)')
      .run(id, formId, parentId, name);
  const addDp = ({ id, form, user = 1, submitted, synced = false, lc = 1 }) =>
    db.raw
      .prepare(
        'INSERT INTO datapoints (id, form, user, submitted, syncedAt, locallyCreated, createdAt) VALUES (?,?,?,?,?,?,?)',
      )
      .run(id, form, user, submitted, synced ? '2026-01-01' : null, lc, '2026-01-01');

  beforeEach(() => {
    addFamForm(10, 100, null, 'Registration'); // registration form
    addFamForm(20, 200, 100, 'Monitoring'); // monitoring child
    addDp({ id: 1, form: 10, submitted: 0 }); // reg draft
    addDp({ id: 2, form: 10, submitted: 1, synced: false }); // reg pending
    addDp({ id: 3, form: 10, submitted: 1, synced: true }); // reg synced
    addDp({ id: 4, form: 10, submitted: 1, synced: true, lc: 0 }); // reg MASTER (downloaded)
    addDp({ id: 5, form: 20, submitted: 1, synced: true }); // monitoring synced
    addDp({ id: 6, form: 20, submitted: 0 }); // monitoring draft
    addDp({ id: 7, form: 10, user: 2, submitted: 1, synced: true }); // other user
  });

  it('countFamilyByStatus counts registration + monitoring, excluding master data and other users', async () => {
    const res = await crudDataPoints.countFamilyByStatus(db, {
      formDbId: 10,
      backendFormId: 100,
      user: 1,
    });
    expect(res).toEqual({ draft: 2, pending: 1, synced: 2 });
  });

  it('getFamilyByStatus(synced) returns family synced rows with group info, registration first', async () => {
    const rows = await crudDataPoints.getFamilyByStatus(db, {
      formDbId: 10,
      backendFormId: 100,
      user: 1,
      status: 'synced',
    });
    expect(rows.map((r) => r.id).sort()).toEqual([3, 5]); // not master (4) nor other user (7)
    expect(rows[0].groupParentId).toBeNull(); // registration group first
    expect(rows.find((r) => r.id === 5)).toMatchObject({ groupName: 'Monitoring', groupParentId: 100 });
  });

  it('getFamilyByStatus(draft) includes monitoring drafts', async () => {
    const rows = await crudDataPoints.getFamilyByStatus(db, {
      formDbId: 10,
      backendFormId: 100,
      user: 1,
      status: 'draft',
    });
    expect(rows.map((r) => r.id).sort()).toEqual([1, 6]);
  });
});
