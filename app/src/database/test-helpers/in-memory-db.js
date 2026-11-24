import Database from 'better-sqlite3';

/**
 * In-memory SQLite exposing the async interface the crud layer (via src/database/sql.js)
 * expects: execAsync / runAsync / getAllAsync / getFirstAsync. Use this for real-SQL crud
 * tests instead of the empty `__mocks__/expo-sqlite.js`, which returns no rows and so can't
 * exercise query logic.
 *
 * better-sqlite3 is synchronous and returns `lastInsertRowid` (lowercase); `sql.insertRow`
 * reads `lastInsertRowId`, so `runAsync` maps it. (dev-only dependency.)
 *
 * This file lives outside `__tests__/` on purpose — jest's testRegex treats every file under
 * `__tests__/` as a test.
 */
export const makeInMemoryDb = () => {
  const raw = new Database(':memory:');
  return {
    raw,
    execAsync: async (sql) => raw.exec(sql),
    runAsync: async (sql, ...params) => {
      // better-sqlite3 rejects `undefined`; expo-sqlite tolerates it. Coerce so partial
      // update objects (fields left undefined) behave as they do on-device.
      const r = raw.prepare(sql).run(...params.map((p) => (p === undefined ? null : p)));
      return { changes: r.changes, lastInsertRowId: Number(r.lastInsertRowid) };
    },
    getAllAsync: async (sql, ...params) => raw.prepare(sql).all(...params),
    getFirstAsync: async (sql, ...params) => raw.prepare(sql).get(...params) ?? null,
  };
};

/** Create the forms + datapoints tables with every column the crud layer touches. */
export const createCrudSchema = (db) => {
  db.raw.exec(`
    CREATE TABLE forms (
      id INTEGER PRIMARY KEY, formId INTEGER, parentId INTEGER, version TEXT, name TEXT,
      json TEXT, latest INTEGER, userId INTEGER, createdAt TEXT
    );
    CREATE TABLE datapoints (
      id INTEGER PRIMARY KEY, form INTEGER, user INTEGER, name TEXT, geo TEXT,
      submitted INTEGER, duration REAL, createdAt TEXT, submittedAt TEXT, syncedAt TEXT,
      json TEXT, repeats INTEGER, uuid TEXT, administrationId INTEGER, draftId INTEGER,
      locallyCreated INTEGER, submissionKey TEXT, sendToWeb INTEGER
    );
  `);
};
