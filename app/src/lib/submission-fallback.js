import * as FileSystem from 'expo-file-system';
import * as Sentry from '@sentry/react-native';
import { openDatabase } from '../database';
import { crudDataPoints } from '../database/crud';
import { UIState } from '../store';
import { LOW_STORAGE_THRESHOLD, LOW_STORAGE_CLEAR_THRESHOLD } from './constants';

const FALLBACK_DIR = `${FileSystem.documentDirectory}pending-submissions`;

const writeRow = async (db, payload, isNewSubmission) =>
  isNewSubmission
    ? crudDataPoints.saveDataPoint(db, payload)
    : crudDataPoints.updateDataPoint(db, payload);

/**
 * Layer 1: the shared connection. Layer 2: a fresh one — this is what survives a
 * closed or stale handle, the failure mode behind the production NullPointerException
 * reports. Layer 3: a JSON file on disk, so the answers outlive the process even when
 * SQLite is unusable (disk full, corruption, locked).
 *
 * Never throws. The return value tells the caller how durable the answers are:
 *   'saved'    — in SQLite
 *   'fallback' — on disk, recovered next launch
 *   'failed'   — memory only, the caller MUST keep the user on the form
 *
 * @param {Object} db - The shared database connection.
 * @param {Object} payload - The datapoint row to write.
 * @param {boolean} isNewSubmission - Insert when true, update when false.
 * @returns {Promise<'saved'|'fallback'|'failed'>}
 */
export const persistSubmission = async (db, payload, isNewSubmission) => {
  try {
    await writeRow(db, payload, isNewSubmission);
    return 'saved';
  } catch (error) {
    Sentry.captureMessage('[persistSubmission] primary connection failed, retrying fresh');
    Sentry.captureException(error);
  }
  try {
    const freshDb = await openDatabase();
    await writeRow(freshDb, payload, isNewSubmission);
    return 'saved';
  } catch (error) {
    Sentry.captureMessage('[persistSubmission] fresh connection failed, writing fallback file');
    Sentry.captureException(error);
  }
  try {
    const { exists } = await FileSystem.getInfoAsync(FALLBACK_DIR);
    if (!exists) {
      await FileSystem.makeDirectoryAsync(FALLBACK_DIR, { intermediates: true });
    }
    // Keyed on the session uuid so a retry overwrites its own file rather than
    // queueing a second copy of the same submission.
    await FileSystem.writeAsStringAsync(
      `${FALLBACK_DIR}/${payload.uuid}.json`,
      JSON.stringify({ payload, isNewSubmission }),
    );
    return 'fallback';
  } catch (error) {
    // The last line of defence failed too — a full disk is the likely cause. The
    // answers now exist only in the Pullstate store, so the caller must keep the
    // user on the form. Reported loudly: this is the case we have never seen.
    Sentry.captureMessage('[persistSubmission] fallback file write failed, answers in memory only');
    Sentry.captureException(error);
    return 'failed';
  }
};

const restoreAll = async (db) => {
  const { exists } = await FileSystem.getInfoAsync(FALLBACK_DIR);
  if (!exists) {
    return 0;
  }
  const files = await FileSystem.readDirectoryAsync(FALLBACK_DIR);
  const results = await Promise.all(
    files.map(async (name) => {
      try {
        const raw = await FileSystem.readAsStringAsync(`${FALLBACK_DIR}/${name}`);
        const { payload, isNewSubmission } = JSON.parse(raw);
        await writeRow(db, payload, isNewSubmission);
        await FileSystem.deleteAsync(`${FALLBACK_DIR}/${name}`, { idempotent: true });
        return 1;
      } catch (error) {
        // Keep the file. A recovery that cannot land the row must not delete the
        // only copy of it — better a retry next launch than silent loss.
        Sentry.captureMessage(`[recoverPendingSubmissions] could not restore ${name}`);
        Sentry.captureException(error);
        return 0;
      }
    }),
  );
  return results.reduce((total, count) => total + count, 0);
};

/**
 * Replays every fallback file into SQLite. Called once per launch, once the
 * connection is known good.
 *
 * @param {Object} db - The database connection.
 * @returns {Promise<number>} How many submissions were restored.
 */
export const recoverPendingSubmissions = async (db) => {
  try {
    return await restoreAll(db);
  } catch (error) {
    // Called from migrateDbIfNeeded, which is SQLiteProvider's onInit — an escape
    // here would fail the whole database setup and take the app down with it.
    Sentry.captureMessage('[recoverPendingSubmissions] recovery sweep failed');
    Sentry.captureException(error);
    return 0;
  }
};

/**
 * Refreshes the low-storage flag behind the status bar warning. Runs where disk
 * usage actually changes — never on a timer.
 */
export const refreshStorageWarning = async () => {
  try {
    const free = await FileSystem.getFreeDiskStorageAsync();
    UIState.update((s) => {
      // Hysteresis: once warned, require a real recovery before standing down.
      // Compression transiently writes a second copy of a photo, so a single
      // threshold would flap the bar on and off during a capture.
      s.lowStorage = s.lowStorage
        ? free < LOW_STORAGE_CLEAR_THRESHOLD
        : free < LOW_STORAGE_THRESHOLD;
    });
  } catch (error) {
    // A failed probe must never block the caller. Leaving the flag untouched is the
    // safe default: a stale warning is harmless, a missed save is not.
    Sentry.captureMessage('[refreshStorageWarning] could not read free disk space');
    Sentry.captureException(error);
  }
};
