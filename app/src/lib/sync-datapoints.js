import { crudDataPoints, crudForms } from '../database/crud';
import sql from '../database/sql';
import api from './api';

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
 * @param {Function} onPageReceived - async callback(pageData, page, totalPage, total)
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
    const { data, total_page: totalPage, current: page, total } = apiData;

    lastTotal = total;
    lastTotalPage = totalPage;
    await onPageReceived(data, page, totalPage, total);
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
 * Downloads and saves a single datapoint's JSON data.
 * Network call is outside the transaction to avoid holding DB lock during I/O.
 *
 * @param {Object} db - database connection
 * @param {Object} datapointInfo - { formId, administrationId, url, lastUpdated }
 * @param {string|number} user - user id
 * @param {Map|null} formCache - optional Map<formId, { dbRecord, parsedGroups }> for caching
 */
export const downloadDatapointsJson = async (
  db,
  { formId, administrationId, url, lastUpdated },
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

  // DB operations INSIDE the transaction
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

    if (existing) {
      await crudDataPoints.updateByUUID(txDb, {
        uuid,
        form: form?.id,
        json: answers,
        syncedAt: lastUpdated,
        repeats: JSON.stringify(repeats),
      });
      return;
    }

    // Insert new datapoint only if it doesn't exist. The local id is left to
    // SQLite: the backend's id draws from the same small-integer space, so
    // reusing it would overwrite an unrelated local row. Identity is uuid + form.
    const datapointData = {
      uuid,
      user,
      geo,
      name,
      administrationId,
      form: form?.id,
      submitted: 1,
      duration: 0,
      createdAt: new Date().toISOString(),
      json: answers,
      syncedAt: lastUpdated,
      repeats: JSON.stringify(repeats),
    };

    await crudDataPoints.saveDataPoint(txDb, datapointData);
  });
};
