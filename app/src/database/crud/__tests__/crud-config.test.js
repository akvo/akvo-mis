import crudConfig from '../crud-config';
import { makeInMemoryDb } from '../../test-helpers/in-memory-db';

let db;

beforeEach(() => {
  db = makeInMemoryDb();
  db.raw.exec(`CREATE TABLE config (
    id INTEGER PRIMARY KEY, appVersion TEXT, authenticationCode TEXT, lang TEXT,
    serverURL TEXT, syncInterval INTEGER, syncWifiOnly INTEGER
  )`);
});

describe('addConfig', () => {
  it('inserts the single config row (id 1)', async () => {
    const id = await crudConfig.addConfig(db, { serverURL: 'URL', lang: 'en' });
    expect(id).toBe(1);
    const row = db.raw.prepare('SELECT * FROM config WHERE id = 1').get();
    expect(row.serverURL).toBe('URL');
    expect(row.lang).toBe('en');
  });
});

describe('getConfig', () => {
  it('returns null when config does not exist', async () => {
    const result = await crudConfig.getConfig(db);
    expect(result).toBeNull();
  });

  it('returns the stored config', async () => {
    await crudConfig.addConfig(db, { serverURL: 'URL', lang: 'en', authenticationCode: 'abc' });
    const result = await crudConfig.getConfig(db);
    expect(result).toMatchObject({ id: 1, serverURL: 'URL', lang: 'en', authenticationCode: 'abc' });
  });
});

describe('updateConfig', () => {
  it('updates the config row', async () => {
    await crudConfig.addConfig(db, { serverURL: 'URL' });
    await crudConfig.updateConfig(db, { serverURL: 'new URL' });
    const row = db.raw.prepare('SELECT serverURL FROM config WHERE id = 1').get();
    expect(row.serverURL).toBe('new URL');
  });
});
