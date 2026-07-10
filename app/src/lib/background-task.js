import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';
import * as Network from 'expo-network';
import * as Sentry from '@sentry/react-native';
import api from './api';
import { openDatabase } from '../database';
import { crudForms, crudDataPoints, crudUsers, crudConfig, crudSyncQueue } from '../database/crud';
import {
  downloadDatapointsJson,
  fetchFormDatapointsPageByPage,
  markSyncComplete,
} from './sync-datapoints';
import notification from './notification';
import crudJobs from '../database/crud/crud-jobs';
import { UIState, DatapointSyncState } from '../store';
import {
  QUESTION_TYPES,
  SYNC_DATAPOINT_BACKGROUND_TASK_NAME,
  SYNC_DATAPOINT_JOB_NAME,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
  SYNC_STATUS,
} from './constants';
import MIME_TYPES from './mime_types';

const BATCH_SIZE = 20;
const UPLOAD_CONCURRENCY = 3;

const syncFormVersion = async (
  db,
  { showNotificationOnly = true, sendPushNotification = () => {} },
) => {
  const { isConnected } = await Network.getNetworkStateAsync();
  if (!isConnected) {
    return;
  }
  try {
    // find last session
    const session = await crudUsers.getActiveUser(db);
    if (!session) {
      return;
    }
    const res = await api.post('/auth?keep_last_synced_at=true', { code: session.password });
    const { data } = res;
    let hasNewForms = false;

    await data.formsUrl.reduce(async (prev, form) => {
      await prev;
      const formExist = await crudForms.selectFormByIdAndVersion(db, { ...form });
      if (formExist) {
        return;
      }
      if (showNotificationOnly) {
        hasNewForms = true;
        return;
      }
      const formRes = await api.get(form.url);
      await crudForms.upsertForm(db, {
        ...form,
        userId: session?.id,
        formJSON: formRes?.data,
      });
    }, Promise.resolve());

    if (hasNewForms && showNotificationOnly) {
      sendPushNotification();
    }
  } catch (err) {
    Sentry.captureMessage('[background-task] syncFormVersion failed');
    Sentry.captureException(err);
  }
};

const registerBackgroundTask = async (TASK_NAME, settingsValue = null) => {
  const db = await openDatabase();
  try {
    const config = await crudConfig.getConfig(db);
    const syncIntervalSec = settingsValue || parseInt(config?.syncInterval, 10) || 3600;
    const intervalMinutes = Math.max(Math.round(syncIntervalSec / 60), 15);
    return await BackgroundTask.registerTaskAsync(TASK_NAME, {
      minimumInterval: intervalMinutes,
    });
  } catch (err) {
    return Promise.reject(err);
  } finally {
    await db.closeAsync();
  }
};

const unregisterBackgroundTask = async (TASK_NAME) => {
  try {
    const res = await BackgroundTask.unregisterTaskAsync(TASK_NAME);
    return res;
  } catch (err) {
    return Promise.reject(err);
  }
};

const backgroundTaskStatus = async (TASK_NAME) => {
  await BackgroundTask.getStatusAsync();
  await TaskManager.isTaskRegisteredAsync(TASK_NAME);
};

const handleOnUploadFiles = async (
  data,
  apiURL = '/images',
  questionTypes = [QUESTION_TYPES.image],
) => {
  // Extract files from submissions
  const allFiles = data.reduce((files, d) => {
    try {
      const answers = JSON.parse(d.json);
      const questions = JSON.parse(d.json_form)?.question_group?.flatMap((qg) => qg.question) || [];
      const questionFiles = questions.filter((q) => questionTypes.includes(q.type));
      if (!questionFiles.length) return files;

      Object.entries(answers).forEach(([key, value]) => {
        const [questionId] = key.split('-');
        const question = questionFiles.find((q) => `${q.id}` === questionId);
        if (question && value?.startsWith('file://')) {
          files.push({ id: key, value, dataID: d.id });
        }
      });
      return files;
    } catch {
      return files;
    }
  }, []);

  if (!allFiles.length) {
    return { uploadedFiles: [], failedDataIDs: new Set() };
  }

  // Prepare lazy upload functions (not executed yet)
  const uploadFns = allFiles.map((f) => () => {
    const extension = f.value.split('.').pop()?.toLowerCase();
    const fileType = MIME_TYPES[extension] || 'application/octet-stream';
    const formData = new FormData();
    formData.append('file', {
      uri: f.value,
      name: `file_${f.id}_${f.dataID}.${extension}`,
      type: fileType,
    });
    return api.post(apiURL, formData, {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'multipart/form-data',
      },
    });
  });

  // Build chunks for concurrency-limited upload
  const chunks = Array.from({ length: Math.ceil(uploadFns.length / UPLOAD_CONCURRENCY) }, (_, i) =>
    uploadFns.slice(i * UPLOAD_CONCURRENCY, (i + 1) * UPLOAD_CONCURRENCY),
  );

  // Execute chunks sequentially, each chunk runs concurrently
  const results = await chunks.reduce(async (prevResults, chunk) => {
    const prev = await prevResults;
    const chunkResults = await Promise.allSettled(chunk.map((fn) => fn()));
    return prev.concat(chunkResults);
  }, Promise.resolve([]));

  const uploadedFiles = [];
  const failedDataIDs = new Set();
  results.forEach((result, i) => {
    if (result.status === 'fulfilled') {
      uploadedFiles.push({ ...allFiles[i], ...result.value.data });
    } else {
      failedDataIDs.add(allFiles[i].dataID);
    }
  });
  return { uploadedFiles, failedDataIDs };
};

// Recursive batch processor: fetches BATCH_SIZE items, processes them,
// then recurses if more remain. Stops on empty result or failures.
const processBatch = async (db, activeJob, session, counts = { success: 0, failed: 0 }) => {
  const data = await crudDataPoints.selectSubmissionToSync(db, BATCH_SIZE);
  if (!data?.length) {
    return counts;
  }

  // Upload files for THIS BATCH only
  // Defensive defaults: under OOM conditions, Hermes can produce incomplete return objects
  // from handleOnUploadFiles. The `|| {}` + default values prevent TypeError on spread.
  const { uploadedFiles: photos = [], failedDataIDs: failedPhotos = new Set() } =
    (await handleOnUploadFiles(data, '/images', [QUESTION_TYPES.image])) || {};
  const { uploadedFiles: attachments = [], failedDataIDs: failedAttachments = new Set() } =
    (await handleOnUploadFiles(data, '/attachments', [QUESTION_TYPES.attachment])) || {};

  const failedUploadIDs = new Set([...failedPhotos, ...failedAttachments]);

  // Process each datapoint sequentially
  await data.reduce(async (previousPromise, d) => {
    await previousPromise;
    if (d?.syncedAt) {
      return;
    }

    // Skip datapoints with failed file uploads — saveAsPending keeps them
    // in the queue so the existing retry paths (timer / manual / background) pick them up
    if (failedUploadIDs.has(d.id)) {
      counts.failed += 1;
      await crudDataPoints.saveAsPending(db, d.id);
      return;
    }

    try {
      const geoVal = d.geo ? { geo: d.geo.split('|')?.map((x) => parseFloat(x)) } : {};
      const answerValues = JSON.parse(d.json.replace(/''/g, "'"));

      // Add photos and attachments to answers
      [...photos, ...attachments]
        .filter((file) => file?.dataID === d.id)
        .forEach((file) => {
          answerValues[file?.id] = file?.file;
        });

      const syncData = {
        formId: d.formId,
        name: d.name,
        duration: Math.round(d.duration),
        submittedAt: d.submittedAt,
        submitter: session.name,
        answers: answerValues,
        uuid: d.uuid,
        ...geoVal,
      };

      // sync data point
      let syncURL = '/sync';
      if (d?.submitted && d?.draftId) {
        syncURL = `/sync?id=${d.draftId}&is_published=true`;
      }
      if (!d?.submitted) {
        syncURL = d?.draftId ? `/sync?id=${d.draftId}&is_draft=true` : '/sync?is_draft=true';
      }
      const res = await api.post(syncURL, syncData);
      if (res.status === 200) {
        await crudDataPoints.markSynced(db, d.id);
      }
      counts.success += 1;
    } catch (error) {
      counts.failed += 1;
      Sentry.captureException(error);
      await crudDataPoints.saveAsPending(db, d.id);
    }
  }, Promise.resolve());

  // If batch was full and no failures, fetch next batch
  if (data.length >= BATCH_SIZE && counts.failed === 0) {
    return processBatch(db, activeJob, session, counts);
  }
  return counts;
};

const syncFormSubmission = async (db, activeJob = {}) => {
  const { isConnected } = await Network.getNetworkStateAsync();
  if (!isConnected) {
    return BackgroundTask.BackgroundTaskResult.Success;
  }
  try {
    const session = await crudUsers.getActiveUser(db);
    api.setToken(session.token);

    const { success: totalSuccess, failed: totalFailed } = await processBatch(
      db,
      activeJob,
      session,
    );

    // Status updates ONCE after all batches
    if (activeJob?.id && totalFailed === 0) {
      await crudJobs.deleteJob(db, activeJob.id);
    }

    if (totalSuccess > 0 && totalFailed === 0) {
      const { inProgress: datapointSyncActive } = DatapointSyncState.getRawState();
      UIState.update((s) => {
        s.isManualSynced = false;
        s.refreshPage = true;
        // Only show success if datapoint sync is not still running
        if (!datapointSyncActive) {
          s.statusBar = {
            type: SYNC_STATUS.success,
            bgColor: '#16a34a',
            icon: 'checkmark-done',
          };
        }
      });
      notification.sendPushNotification(SYNC_FORM_SUBMISSION_TASK_NAME);
    }

    if (totalFailed > 0) {
      UIState.update((s) => {
        s.isManualSynced = false;
        s.statusBar = {
          type: SYNC_STATUS.failed,
          bgColor: '#ec003f',
          icon: 'alert-sharp',
          failedCount: totalFailed,
        };
      });
    }

    return BackgroundTask.BackgroundTaskResult.Success;
  } catch (error) {
    Sentry.captureMessage(`[background-task] syncFormSubmission failed`);
    Sentry.captureException(error);

    if (activeJob?.id) {
      await crudJobs.deleteJob(db, activeJob.id);
    }

    return Promise.reject(
      new Error(
        `syncFormSubmission failed (${error?.response?.status || 'unknown'}): ${error?.message}`,
      ),
    );
  }
};

const backgroundTaskHandler = () => ({
  syncFormVersion,
  registerBackgroundTask,
  unregisterBackgroundTask,
  backgroundTaskStatus,
  syncFormSubmission,
});

const backgroundTask = backgroundTaskHandler();

export const defineSyncFormVersionTask = () =>
  TaskManager.defineTask(SYNC_FORM_VERSION_TASK_NAME, async () => {
    const db = await openDatabase();
    try {
      await syncFormVersion(db, {
        sendPushNotification: notification.sendPushNotification,
        showNotificationOnly: true,
      });
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch (err) {
      Sentry.captureMessage(`[${SYNC_FORM_VERSION_TASK_NAME}] defineSyncFormVersionTask failed`);
      Sentry.captureException(err);
      return BackgroundTask.BackgroundTaskResult.Failed;
    } finally {
      await db.closeAsync();
    }
  });

/**
 * Background datapoint sync: processes ONE form at a time, saves progress.
 * Each background trigger continues from where the last one left off.
 */
const syncDatapointsBackground = async () => {
  const db = await openDatabase();
  try {
    const session = await crudUsers.getActiveUser(db);
    if (!session?.token) {
      return;
    }
    api.setToken(session.token);

    const activeJob = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);
    if (!activeJob) {
      return;
    }

    const incompleteForms = await crudSyncQueue.getIncompleteForms(db);
    if (!incompleteForms.length) {
      await crudJobs.deleteJob(db, activeJob.id);
      try {
        await markSyncComplete();
        await crudSyncQueue.clearQueue(db);
      } catch (err) {
        Sentry.captureException(err);
      }
      return;
    }

    // Process first incomplete form only (time-limited by OS)
    const queueRow = incompleteForms[0];
    const { formId } = queueRow;
    const startPage = queueRow.lastPage + 1;
    const formCache = new Map();

    await fetchFormDatapointsPageByPage(
      formId,
      async (pageData, page, totalPage, total) => {
        if (page === startPage) {
          await crudSyncQueue.upsertQueue(db, [
            {
              formId,
              totalPage,
              totalData: total,
            },
          ]);
        }
        let pageHasErrors = false;
        await pageData.reduce(async (prev, item) => {
          await prev;
          try {
            await downloadDatapointsJson(
              db,
              {
                url: item.url,
                formId: item.form_id,
                administrationId: item.administration_id,
                lastUpdated: item.last_updated,
              },
              session.id,
              formCache,
            );
          } catch (err) {
            pageHasErrors = true;
            Sentry.captureException(err);
          }
        }, Promise.resolve());
        // Only advance page if all items succeeded
        if (!pageHasErrors) {
          await crudSyncQueue.updateLastPage(db, formId, page);
        }
      },
      startPage,
      100,
    );

    formCache.clear();
  } catch (err) {
    Sentry.captureException(err);
  } finally {
    await db.closeAsync();
  }
};

export const defineSyncDatapointBackgroundTask = () =>
  TaskManager.defineTask(SYNC_DATAPOINT_BACKGROUND_TASK_NAME, async () => {
    try {
      await syncDatapointsBackground();
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch (err) {
      Sentry.captureException(err);
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });

export const defineSyncFormSubmissionTask = () => {
  TaskManager.defineTask(SYNC_FORM_SUBMISSION_TASK_NAME, async () => {
    const db = await openDatabase();
    try {
      await syncFormSubmission(db);
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch (err) {
      Sentry.captureMessage(
        `[${SYNC_FORM_SUBMISSION_TASK_NAME}] defineSyncFormSubmissionTask failed`,
      );
      Sentry.captureException(err);
      return BackgroundTask.BackgroundTaskResult.Failed;
    } finally {
      await db.closeAsync();
    }
  });
};

export default backgroundTask;
