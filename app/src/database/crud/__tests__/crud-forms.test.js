/**
 * Real-SQL tests (better-sqlite3 in-memory). The crud layer takes `db` as its first arg and
 * uses the async API (getAllAsync/runAsync); these tests seed real rows and assert behaviour.
 * Deep count logic lives in crud-forms-counts.test.js.
 */
import crudForms from '../crud-forms';
import { makeInMemoryDb, createCrudSchema } from '../../test-helpers/in-memory-db';

let db;

beforeEach(() => {
  db = makeInMemoryDb();
  createCrudSchema(db);
});

describe('addForm', () => {
  it('inserts the form as the latest version', async () => {
    const id = await crudForms.addForm(db, {
      userId: 1,
      id: 123,
      version: '1.0.0',
      formJSON: { id: 123, version: 1, name: 'Form 1' },
    });
    expect(id).toBeGreaterThan(0);
    const row = db.raw.prepare('SELECT * FROM forms WHERE formId = 123').get();
    expect(row.name).toBe('Form 1');
    expect(row.latest).toBe(1);
    expect(row.userId).toBe(1);
  });
});

describe('selectLatestFormVersion', () => {
  it('returns [] when the user has no forms', async () => {
    const result = await crudForms.selectLatestFormVersion(db, { user: 99 });
    expect(result).toEqual([]);
  });

  it('returns the latest parent form with zeroed counts when it has no datapoints', async () => {
    db.raw
      .prepare('INSERT INTO forms (id, formId, parentId, version, name, json, latest, userId) VALUES (?,?,?,?,?,?,?,?)')
      .run(1, 123, null, '1.0.0', 'Form Test', '{}', 1, 1);
    const [row] = await crudForms.selectLatestFormVersion(db, { user: 1 });
    expect(row.formId).toBe(123);
    expect(row.name).toBe('Form Test');
    expect(row).toMatchObject({ draft: 0, submitted: 0, synced: 0, registered: 0, subFormCount: 0 });
  });

  it('skips non-latest versions', async () => {
    db.raw
      .prepare('INSERT INTO forms (id, formId, parentId, version, name, json, latest, userId) VALUES (?,?,?,?,?,?,?,?)')
      .run(1, 123, null, '1.0.0', 'Old', '{}', 0, 1);
    const result = await crudForms.selectLatestFormVersion(db, { user: 1 });
    expect(result).toEqual([]);
  });
});

describe('selectFormByIdAndVersion', () => {
  beforeEach(() => {
    db.raw
      .prepare('INSERT INTO forms (id, formId, parentId, version, name, json, latest, userId) VALUES (?,?,?,?,?,?,?,?)')
      .run(1, 123, null, '1.0.0', 'Form Test', '{}', 1, 1);
  });

  it('returns [] when no matching version exists', async () => {
    const result = await crudForms.selectFormByIdAndVersion(db, { id: 123, version: '1.0.1' });
    expect(result).toEqual([]);
  });

  it('returns the matching form', async () => {
    const result = await crudForms.selectFormByIdAndVersion(db, { id: 123, version: '1.0.0' });
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Form Test');
  });
});

describe('selectFormById', () => {
  it('returns the form for a valid local id', async () => {
    db.raw
      .prepare('INSERT INTO forms (id, formId, parentId, version, name, json, latest, userId) VALUES (?,?,?,?,?,?,?,?)')
      .run(1, 123, null, '1.0.0', 'Form 1', '{"question_group":[]}', 1, 1);
    const result = await crudForms.selectFormById(db, { id: 1 });
    expect(result.name).toBe('Form 1');
    expect(result.formId).toBe(123);
  });

  it('returns null for a missing id', async () => {
    const result = await crudForms.selectFormById(db, { id: 404 });
    expect(result).toBeNull();
  });
});
