import * as Sentry from '@sentry/react-native';
import { crudConfig, crudDataPoints, crudForms, crudJobs, crudSyncQueue } from '../database/crud';
import sql from '../database/sql';
import api from './api';
import { jobStatus, SYNC_DATAPOINT_JOB_NAME } from './constants';
import DatapointSyncState from '../store/datapoint-sync';
import { finishDatapointSync, writeIndexFromListGeometry } from './geometry-index-writer';

/**
 * Iteratively fetches datapoints page by page, calling the processor callback
 * for each page's data before fetching the next page.
 * Uses page_size=100 (backend max) to reduce HTTP round-trips.
 *
 * @param {Function} onPageReceived - async callback(pageData, pageNumber, totalPages)
 * @param {number} pageSize - page size to request (default 100, backend max)
 * @returns {Promise<{totalProcessed: number}>}
 */
export const fetchDatapointsPageByPage = async (onPageReceived, pageSize = 100) => {
  let totalProcessed = 0;

  // Async recursion is stack-safe: each `await` unwinds the call frame,
  // so recursion depth equals 1 regardless of page count.
  // At page_size=100, 10,000 datapoints = 100 pages.
  const fetchPage = async (currentPage, totalPages) => {
    if (currentPage > totalPages) {
      return;
    }
    const { data: apiData } = await api.get(
      `/datapoint-list?page=${currentPage}&page_size=${pageSize}`,
    );
    const { data, total_page: totalPage, current: page } = apiData;

    await onPageReceived(data, page, totalPage);
    totalProcessed += data.length;
    await fetchPage(page + 1, totalPage);
  };

  await fetchPage(1, 1);
  return { totalProcessed };
};

/**
 * Iteratively fetches draft datapoints page by page.
 *
 * @param {Function} onPageReceived - async callback(pageData, pageNumber, totalPages)
 * @param {number} pageSize - page size to request (default 100, backend max)
 * @returns {Promise<{totalProcessed: number}>}
 */
export const fetchDraftDatapointsPageByPage = async (onPageReceived, pageSize = 100) => {
  let totalProcessed = 0;

  // Async recursion is stack-safe: each `await` unwinds the call frame,
  // so recursion depth equals 1 regardless of page count.
  // At page_size=100, 10,000 datapoints = 100 pages.
  const fetchPage = async (currentPage, totalPages) => {
    if (currentPage > totalPages) {
      return;
    }
    const { data: apiData } = await api.get(
      `/draft-list?page=${currentPage}&page_size=${pageSize}`,
    );
    const { data, total_page: totalPage, current: page } = apiData;

    await onPageReceived(data, page, totalPage);
    totalProcessed += data.length;
    await fetchPage(page + 1, totalPage);
  };

  await fetchPage(1, 1);
  return { totalProcessed };
};

/**
 * Fetches datapoints for a single form page by page using form_id filter.
 * Only one page of data is in memory at a time, reducing peak memory usage.
 *
 * @param {number} formId - backend form ID to filter by
 * @param {Function} onPageReceived - async callback(pageData, page, totalPage, total, complete)
 * @param {number} startPage - page to start from (for resume, default 1)
 * @param {number} pageSize - page size to request (default 100, backend max)
 * @returns {Promise<{totalProcessed: number, totalPage: number, total: number}>}
 */
export const fetchFormDatapointsPageByPage = async (
  formId,
  onPageReceived,
  startPage = 1,
  pageSize = 100,
) => {
  let totalProcessed = 0;
  let lastTotal = 0;
  let lastTotalPage = 0;

  const fetchPage = async (currentPage, totalPages) => {
    if (currentPage > totalPages) {
      return;
    }
    const { data: apiData } = await api.get(
      `/datapoint-list?form_id=${formId}&page=${currentPage}&page_size=${pageSize}`,
    );
    const { data, total_page: totalPage, current: page, total, complete } = apiData;

    lastTotal = total;
    lastTotalPage = totalPage;
    await onPageReceived(data, page, totalPage, total, complete);
    totalProcessed += data.length;
    await fetchPage(page + 1, totalPage);
  };

  await fetchPage(startPage, startPage);
  return { totalProcessed, totalPage: lastTotalPage, total: lastTotal };
};

/**
 * Marks datapoint sync as complete on the backend.
 * Updates last_synced_at so the next sync only gets new/updated datapoints.
 */
export const markSyncComplete = async () => {
  await api.post('/sync-complete');
};

/**
 * Full datapoint sync finished — readiness flag + backend cursor + queue clear.
 * Single call site for SyncService and the background task (GEO-006 §10).
 */
export const onDatapointSyncFinished = async (db) =>
  finishDatapointSync(db, {
    markSyncComplete,
    clearQueue: crudSyncQueue.clearQueue,
  });

/**
 * Finish the sync **and** retire its job — in that order, and only together.
 *
 * Deleting the job first, or deleting it regardless of whether the finish step threw, wedges
 * overlap validation permanently. `finishDatapointSync` posts the backend cursor, clears the
 * queue and sets `geometryIndexReady` last (GEO-006 D-4); if the post fails, the queue survives
 * marked complete while readiness stays `0`. With the job gone, the next run's quick-check finds
 * a complete queue and no new data, retires itself, and never reaches the finish step again —
 * so GEO-007 refuses to validate for good, and only a Reset clears it.
 *
 * Throwing rather than swallowing is the point: the caller keeps the job PENDING so the next
 * tick retries, and `MAX_ATTEMPT` still retires a job whose finish step never succeeds.
 */
export const completeDatapointSync = async (db, activeJob) => {
  await onDatapointSyncFinished(db);
  await crudJobs.deleteJob(db, activeJob.id);
};

/**
 * Did a previous run leave the finish step half-done?
 *
 * Only meaningful where the queue is present and complete: a cleared queue means the finish
 * step got as far as clearing it, and an empty one on a fresh install has never had a sync to
 * finish. In that narrow spot `geometryIndexReady !== 1` means the readiness update never
 * landed, and the run must retry it instead of retiring the job as "nothing to do".
 */
export const datapointSyncFinishPending = async (db) => {
  const config = await crudConfig.getConfig(db);
  return config?.geometryIndexReady !== 1;
};

/**
 * Downloads and saves a single datapoint's JSON data.
 * Network call is outside the transaction to avoid holding DB lock during I/O.
 * Geometry index rows are written inside the same transaction as the datapoint
 * (GEO-006 D-6), from the list payload's precomputed bbox — no extra fetch.
 *
 * @param {Object} db - database connection
 * @param {Object} datapointInfo - { formId, administrationId, url, lastUpdated, geometry, name, isComplete }
 * @param {string|number} user - user id
 * @param {Map|null} formCache - optional Map<formId, { dbRecord, parsedGroups }> for caching
 */
export const downloadDatapointsJson = async (
  db,
  { formId, administrationId, url, lastUpdated, geometry, name: listName, isComplete },
  user,
  formCache = null,
) => {
  // Resolve form from cache FIRST (before any network call)
  let form;
  let parsedGroups;

  if (formCache?.has(formId)) {
    ({ dbRecord: form, parsedGroups } = formCache.get(formId));
  } else {
    form = await crudForms.getByFormId(db, { formId });
    parsedGroups = JSON.parse(form?.json || '{}')?.question_group || [];
    formCache?.set(formId, { dbRecord: form, parsedGroups });
  }

  // Skip-unchanged: check if local datapoint is already up-to-date
  const uuid = url.split('/').pop().replace('.json', '');
  const existing = await crudDataPoints.getByUUID(db, { uuid, form: form?.id });
  // Never clobber a local row with pending changes (syncedAt NULL): it is
  // queued for upload and its answers are newer than the server copy —
  // overwriting would lose the edits AND falsely mark them as synced
  if (existing && !existing.syncedAt) {
    return;
  }
  if (existing?.syncedAt && lastUpdated && existing.syncedAt >= lastUpdated) {
    return;
  }

  // Network call OUTSIDE the transaction
  const response = await api.get(url);
  if (response.status !== 200) {
    return;
  }

  const jsonData = response.data;
  const { datapoint_name: name, geolocation: geo, answers } = jsonData || {};
  // A missing file on the server comes back as the web app's index.html with
  // HTTP 200, so `answers` is undefined. Storing that would leave a datapoint
  // with a NULL json column that crashes every screen reading it. Skip it;
  // the next sync retries because no local row was written.
  if (!answers || typeof answers !== 'object') {
    Sentry.captureMessage(`[sync-datapoints] no answers in datapoint file, skipped: ${url}`);
    return;
  }

  const datapointName = name || listName || null;

  // DB operations INSIDE the transaction — datapoint + geometry_index together
  await sql.withTransaction(db, async (txDb) => {
    const repeats = {};
    let repeatIndex = 0;
    parsedGroups.forEach((group) => {
      if (group.repeatable) {
        const qIDs = group.question.map((q) => `${q.id}`);
        const maxRepeats = Object.keys(answers)
          .filter((k) => k?.includes('-'))
          .filter((k) => {
            const [qId] = k.split('-');
            return qIDs.includes(qId);
          })
          .reduce((acc, key) => {
            const match = key.match(/-(\d+)$/);
            if (match) {
              const num = parseInt(match[1], 10);
              return Math.max(acc, num);
            }
            return acc;
          }, 0);
        repeats[repeatIndex] = Array.from({ length: maxRepeats + 1 }, (_, i) => i);
        repeatIndex += 1;
      }
    });

    let datapointId = existing?.id;

    if (existing) {
      await crudDataPoints.updateByUUID(txDb, {
        uuid,
        form: form?.id,
        json: answers,
        syncedAt: lastUpdated,
        repeats: JSON.stringify(repeats),
      });
    } else {
      // Insert new datapoint only if it doesn't exist. The local id is left to
      // SQLite: the backend's id draws from the same small-integer space, so
      // reusing it would overwrite an unrelated local row. Identity is uuid + form.
      const datapointData = {
        uuid,
        user,
        geo,
        name: datapointName,
        administrationId,
        form: form?.id,
        submitted: 1,
        duration: 0,
        createdAt: new Date().toISOString(),
        json: answers,
        syncedAt: lastUpdated,
        repeats: JSON.stringify(repeats),
      };

      datapointId = await crudDataPoints.saveDataPoint(txDb, datapointData);
    }

    // Index write only when the list carried geometry (detectOverlaps forms).
    // Absent geometry → no indexing work for this form.
    if (geometry !== undefined && geometry !== null) {
      await writeIndexFromListGeometry(txDb, {
        uuid,
        formId,
        datapointId,
        name: datapointName,
        geometry,
        isComplete: Boolean(isComplete),
      });
    }
  });
};

/**
 * Ask for a datapoint sync from somewhere that is not the Home screen.
 *
 * GEO-007 D-10 offers **Retry** when the overlap candidate set is incomplete, and Retry has to
 * do what the Home sync button does. Adding the job only when none is active matters: a second
 * job would race the running one and both would write the same rows.
 *
 * ponytail: Home still inlines its own copy of this, together with the form-submission job it
 * also queues. Worth collapsing into here, but not while the only change under test is the
 * overlap path.
 */
export const requestDatapointSync = async (db, userId) => {
  const existing = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);
  if (!existing) {
    await crudJobs.addJob(db, {
      user: userId,
      type: SYNC_DATAPOINT_JOB_NAME,
      status: jobStatus.PENDING,
    });
  }
  DatapointSyncState.update((s) => {
    s.added = true;
    s.inProgress = true;
  });
};
