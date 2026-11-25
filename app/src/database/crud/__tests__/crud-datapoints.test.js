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
