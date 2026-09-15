/* eslint-disable no-console */
import * as FileSystem from 'expo-file-system';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';

import api from './api';

const DIR_NAME = 'SQLite';

const createSqliteDir = async () => {
  /**
   * Setup sqlite directory to save cascades sqlite from server
   */
  if (!(await FileSystem.getInfoAsync(FileSystem.documentDirectory + DIR_NAME)).exists) {
    await FileSystem.makeDirectoryAsync(FileSystem.documentDirectory + DIR_NAME);
  }
};

const download = async (downloadUrl, fileUrl, update = false) => {
  const fileSql = fileUrl?.split('/')?.pop(); // get last segment as filename
  const pathSql = `${DIR_NAME}/${fileSql}`;
  const { exists } = await FileSystem.getInfoAsync(FileSystem.documentDirectory + pathSql);
  if (exists && update) {
    await SQLite.deleteDatabaseAsync(fileSql);
  }
  if (!exists || update) {
    /**
     * The sqlite endpoint resolves the tenant from the assignment token and
     * serves that tenant's file, so the download must carry the token the
     * rest of the api client already sends. Without it the request 401s.
     */
    await FileSystem.downloadAsync(downloadUrl, FileSystem.documentDirectory + pathSql, {
      cache: false,
      headers: api.getConfig().headers,
    });
  }
};

const loadDataSource = async (source, id = null) => {
  const { file: cascadeName } = source;
  const db = await SQLite.openDatabaseAsync(cascadeName, { useNewConnection: true });
  try {
    const sql = id ? 'SELECT * FROM nodes WHERE id = ?' : 'SELECT * FROM nodes';
    const statement = await db.prepareAsync(sql);
    try {
      const result = id ? await statement.executeAsync([id]) : await statement.executeAsync();
      const rows = await result.getAllAsync();
      await result.resetAsync();
      return id ? rows[0] ?? null : rows;
    } catch (error) {
      Sentry.captureMessage('[cascades] Unable to load cascade sqlite');
      Sentry.captureException(error, {
        extra: {
          source,
          id,
        },
      });
      return Promise.reject(error);
    } finally {
      await statement.finalizeAsync();
    }
  } finally {
    await db.closeAsync();
  }
};

const dropFiles = async () => {
  const Sqlfiles = await FileSystem.readDirectoryAsync(FileSystem.documentDirectory + DIR_NAME);
  await Sqlfiles.reduce(async (prev, file) => {
    await prev;
    if (file.includes('sqlite')) {
      const fileUri = `${FileSystem.documentDirectory}${DIR_NAME}/${file}`;
      await FileSystem.deleteAsync(fileUri, { idempotent: true });
    }
  }, Promise.resolve());
  return Sqlfiles;
};

const cascades = {
  createSqliteDir,
  loadDataSource,
  download,
  dropFiles,
  DIR_NAME,
};

export default cascades;
