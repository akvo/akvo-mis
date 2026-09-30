import * as FileSystem from 'expo-file-system';
import * as Sentry from '@sentry/react-native';
import { openDatabase } from '../database';
import { crudDataPoints, crudForms } from '../database/crud';
import sql from '../database/sql';
import { writeIndexFromAnswers } from './geometry-index-writer';
import { UIState } from '../store';
import { LOW_STORAGE_THRESHOLD, LOW_STORAGE_CLEAR_THRESHOLD } from './constants';

const FALLBACK_DIR = `${FileSystem.documentDirectory}pending-submissions`;

/**
 * Write the datapoint and its geometry index rows together, or not at all.
 *
 * GEO-006 D-6 makes `geometry_index` a subset of `datapoints` by construction, and GEO-007
 * relies on that: a candidate with no answers is read as drift and refuses validation. The
 * local save used to write the index *after* this returned, swallowing failures — so a crash,
 * or simply an index error, left a polygon in `datapoints` with nothing in the index. Overlap
 * checks then measured against a set quietly missing a plot.
 *
 * `geometry` is optional: a form with no overlap-enabled geoshape passes nothing and takes the
 * plain single-statement path.
 */
const writeRow = async (db, payload, isNewSubmission, geometry = null) => {
  if (!geometry?.formId || !geometry?.formJson) {
    return isNewSubmission
      ? crudDataPoints.saveDataPoint(db, payload)
      : crudDataPoints.updateDataPoint(db, payload);
  }
  return sql.withTransaction(db, async (txDb) => {
    const datapointId = isNewSubmission
      ? await crudDataPoints.saveDataPoint(txDb, payload)
      : await crudDataPoints.updateDataPoint(txDb, payload).then(() => payload.id);
    await writeIndexFromAnswers(txDb, {
      uuid: payload.uuid,
      formId: geometry.formId,
      datapointId,
      name: payload.name,
      answers: payload.json,
      formJson: geometry.formJson,
      isComplete: true,
    });
    return datapointId;
  });
};

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
export const persistSubmission = async (db, payload, isNewSubmission, geometry = null) => {
  try {
    await writeRow(db, payload, isNewSubmission, geometry);
    return 'saved';
  } catch (error) {
    Sentry.captureMessage('[persistSubmission] primary connection failed, retrying fresh');
    Sentry.captureException(error);
  }
  try {
    const freshDb = await openDatabase();
    await writeRow(freshDb, payload, isNewSubmission, geometry);
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
      /**
       * Only the form id, never the form definition: it is large, and recovery can look it up.
       * Without it the replay would restore the datapoint and leave the index short — the same
       * gap this function was changed to close.
       */
      JSON.stringify({ payload, isNewSubmission, formId: geometry?.formId || null }),
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
        const { payload, isNewSubmission, formId } = JSON.parse(raw);
        // Rebuild the index alongside the datapoint; the form definition comes from the
        // forms table rather than the fallback file, which keeps the file small.
        let geometry = null;
        if (formId) {
          const form = await crudForms.getByFormId(db, { formId });
          if (form?.json) {
            geometry = { formId, formJson: JSON.parse(form.json) };
          }
        }
        await writeRow(db, payload, isNewSubmission, geometry);
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
