import * as SQLite from 'expo-sqlite';
import { DATABASE_NAME } from '../lib/constants';

export { default as tables } from './tables';

/**
 * Opens a dedicated connection to the app database with PRAGMAs applied.
 * busy_timeout makes concurrent writers wait instead of failing immediately
 * with "database is locked" (the app uses multiple connections: the
 * SQLiteProvider one plus background-task connections).
 *
 * @returns {Promise<Object>} The database connection object.
 */
export const openDatabase = async () => {
  const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
    useNewConnection: true,
  });
  await db.execAsync('PRAGMA busy_timeout = 5000;');
  return db;
};
