import crudSessions from '../crud-sessions';
import { makeInMemoryDb } from '../../test-helpers/in-memory-db';

let db;

beforeEach(() => {
  db = makeInMemoryDb();
  db.raw.exec('CREATE TABLE sessions (id INTEGER PRIMARY KEY, token TEXT, passcode TEXT)');
});

describe('addSession', () => {
  it('inserts the session and returns its id', async () => {
    const id = await crudSessions.addSession(db, { token: 'Bearer abcefg', passcode: '123456' });
    expect(id).toBeGreaterThan(0);
    const row = db.raw.prepare('SELECT * FROM sessions WHERE id = ?').get(id);
    expect(row.token).toBe('Bearer abcefg');
  });
});

describe('selectLastSession', () => {
  it('returns undefined when no session exists', async () => {
    const result = await crudSessions.selectLastSession(db);
    expect(result).toBeUndefined();
  });

  it('returns the most recently inserted session', async () => {
    await crudSessions.addSession(db, { token: 'Bearer 1', passcode: '123' });
    await crudSessions.addSession(db, { token: 'Bearer 2', passcode: '321' });
    const result = await crudSessions.selectLastSession(db);
    expect(result).toMatchObject({ token: 'Bearer 2', passcode: '321' });
  });
});
