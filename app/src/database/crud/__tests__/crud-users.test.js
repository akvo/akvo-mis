import crudUsers from '../crud-users';
import { makeInMemoryDb } from '../../test-helpers/in-memory-db';

let db;

const addUser = ({ name, password = 'password', active = 0 }) =>
  db.raw
    .prepare('INSERT INTO users (name, password, active) VALUES (?,?,?)')
    .run(name, password, active);

beforeEach(() => {
  db = makeInMemoryDb();
  db.raw.exec(
    'CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, password TEXT, active INTEGER, lastSyncedAt TEXT)',
  );
});

describe('getActiveUser', () => {
  it('returns null when no active user exists', async () => {
    addUser({ name: 'Jane', active: 0 });
    const result = await crudUsers.getActiveUser(db);
    expect(result).toBeNull();
  });

  it('returns the active user', async () => {
    addUser({ name: 'John', active: 1 });
    addUser({ name: 'Jane', active: 0 });
    const result = await crudUsers.getActiveUser(db);
    expect(result).toMatchObject({ name: 'John', active: 1 });
  });
});

describe('addNew / checkPasscode', () => {
  it('inserts a user and finds it by passcode', async () => {
    const id = await crudUsers.addNew(db, { name: 'John', password: 'secret', active: 1 });
    expect(id).toBeGreaterThan(0);
    const found = await crudUsers.checkPasscode(db, 'secret');
    expect(found).toMatchObject({ name: 'John' });
  });
});

describe('updateLastSynced', () => {
  it('stamps lastSyncedAt on the user', async () => {
    addUser({ name: 'John', active: 1 });
    await crudUsers.updateLastSynced(db, 1);
    const row = db.raw.prepare('SELECT lastSyncedAt FROM users WHERE id = 1').get();
    expect(row.lastSyncedAt).toBeTruthy();
  });
});
