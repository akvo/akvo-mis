import { useCallback, useEffect, useRef } from 'react';
import * as Network from 'expo-network';
import { useSQLiteContext } from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import { BuildParamsState, DatapointSyncState, UIState, UserState } from '../store';
import { backgroundTask } from '../lib';
import crudJobs from '../database/crud/crud-jobs';
import { crudConfig, crudDataPoints, crudForms, crudSyncQueue } from '../database/crud';
import {
  downloadDatapointsJson,
  fetchFormDatapointsPageByPage,
  fetchDraftDatapointsPageByPage,
  markSyncComplete,
} from '../lib/sync-datapoints';
import {
  jobStatus,
  MAX_ATTEMPT,
  SYNC_DATAPOINT_JOB_NAME,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_STATUS,
} from '../lib/constants';

/**
 * This sync only works in the foreground service
 */
const SyncService = () => {
  const isOnline = UIState.useState((s) => s.online);
  const isManualSynced = UIState.useState((s) => s.isManualSynced);
  const syncInterval = BuildParamsState.useState((s) => s.dataSyncInterval);
  const syncInSecond = parseInt(syncInterval, 10) * 1000;
  const userId = UserState.useState((s) => s.id);
  const db = useSQLiteContext();
  const syncLockRef = useRef(false);
  const onSyncLockRef = useRef(false);
  const syncFailureCount = useRef(0);

  const onSync = useCallback(async () => {
    if (onSyncLockRef.current) {
      return;
    }
    onSyncLockRef.current = true;
    try {
      let activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
      const pendingToSync = await crudDataPoints.selectSubmissionToSync(db, 1);
      // if pendingToSync exists but activeJob is null then create new one
      if (!activeJob && pendingToSync?.length) {
        await crudJobs.addJob(db, {
          user: userId,
          type: SYNC_FORM_SUBMISSION_TASK_NAME,
          status: jobStatus.PENDING,
        });

        activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
      }

      // No pending data → clean up the job
      if (!pendingToSync?.length && activeJob) {
        await crudJobs.deleteJob(db, activeJob.id);
        return;
      }

      if (!activeJob) {
        return;
      }

      // Check network constraints
      const settings = await crudConfig.getConfig(db);
      const { type: networkType } = await Network.getNetworkStateAsync();
      if (settings?.syncWifiOnly && networkType !== Network.NetworkStateType.WIFI) {
        return;
      }

      // Stale job detection: if ON_PROGRESS, it may be stuck (app crashed)
      if (activeJob.status === jobStatus.ON_PROGRESS) {
        if (activeJob.attempt >= MAX_ATTEMPT) {
          await crudJobs.deleteJob(db, activeJob.id);
          UIState.update((s) => {
            s.statusBar = {
              type: SYNC_STATUS.failed,
              bgColor: '#ec003f',
              icon: 'alert',
            };
          });
        } else {
          await crudJobs.updateJob(db, activeJob.id, {
            status: jobStatus.PENDING,
            attempt: activeJob.attempt + 1,
          });
          UIState.update((s) => {
            s.statusBar = {
              type: SYNC_STATUS.re_sync,
              bgColor: '#d97706',
              icon: 'repeat',
            };
          });
        }
        return;
      }

      // Zombie job: PENDING with retries exhausted is never executed but
      // still blocks new jobs from being created — delete it so the next
      // sync tick starts fresh with attempt 0
      if (activeJob.status === jobStatus.PENDING && activeJob.attempt >= MAX_ATTEMPT) {
        await crudJobs.deleteJob(db, activeJob.id);
        return;
      }

      // PENDING → execute sync
      if (activeJob.status === jobStatus.PENDING && activeJob.attempt < MAX_ATTEMPT) {
        UIState.update((s) => {
          s.statusBar = {
            type: SYNC_STATUS.on_progress,
            bgColor: '#2563eb',
            icon: 'sync',
          };
        });
        await crudJobs.updateJob(db, activeJob.id, {
          status: jobStatus.ON_PROGRESS,
        });
        await backgroundTask.syncFormSubmission(db, activeJob);
      }
    } finally {
      onSyncLockRef.current = false;
    }
  }, [db, userId]);

  useEffect(() => {
    if (!syncInSecond || !isOnline) {
      return;
    }
    const syncTimer = setInterval(() => {
      onSync()
        .then(() => {
          syncFailureCount.current = 0;
        })
        .catch((err) => {
          syncFailureCount.current += 1;
          const count = syncFailureCount.current;
          if (count === 1 || count % 10 === 0) {
            Sentry.withScope((scope) => {
              scope.setTag('component', 'SyncService');
              scope.setTag('trigger', 'interval');
              scope.setExtra('consecutiveFailures', count);
              scope.setExtra('syncIntervalMs', syncInSecond);
              Sentry.captureException(err);
            });
          }
        });
    }, syncInSecond);

    // eslint-disable-next-line consistent-return
    return () => clearInterval(syncTimer);
  }, [syncInSecond, isOnline, onSync]);

  const onSyncDataPoint = useCallback(async () => {
    const SYNC_PAGE_SIZE = 100;
    const activeJob = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);

    DatapointSyncState.update((s) => {
      s.added = false;
      s.inProgress = !!activeJob;
      s.syncingFormId = null;
      s.formProgress = {};
    });

    if (!activeJob) {
      return;
    }

    // Stale job detection: if ON_PROGRESS, it may be stuck (app was killed mid-sync)
    if (activeJob.status === jobStatus.ON_PROGRESS) {
      if (activeJob.attempt >= MAX_ATTEMPT) {
        await crudJobs.deleteJob(db, activeJob.id);
        DatapointSyncState.update((s) => {
          s.inProgress = false;
          s.progress = 0;
          s.syncingFormId = null;
          s.formProgress = {};
        });
        return;
      }
      // Reset to PENDING so the queue can resume
      await crudJobs.updateJob(db, activeJob.id, {
        status: jobStatus.PENDING,
        attempt: activeJob.attempt + 1,
      });
    }

    if (activeJob.status !== jobStatus.PENDING && activeJob.status !== jobStatus.ON_PROGRESS) {
      return;
    }
    if (activeJob.attempt >= MAX_ATTEMPT) {
      await crudJobs.deleteJob(db, activeJob.id);
      DatapointSyncState.update((s) => {
        s.inProgress = false;
        s.progress = 0;
        s.syncingFormId = null;
        s.formProgress = {};
      });
      return;
    }

    await crudJobs.updateJob(db, activeJob.id, {
      status: jobStatus.ON_PROGRESS,
    });

    UIState.update((s) => {
      s.statusBar = {
        type: SYNC_STATUS.on_progress,
        bgColor: '#2563eb',
        icon: 'sync',
      };
    });

    try {
      // Get registration forms from local SQLite
      const registrationForms = await crudForms.selectLatestFormVersion(db, {
        user: activeJob.user,
      });

      if (!registrationForms?.length) {
        await crudJobs.deleteJob(db, activeJob.id);
        DatapointSyncState.update((s) => {
          s.inProgress = false;
          s.progress = 0;
        });
        return;
      }

      // Quick check: if queue has completed entries and all local counts match, skip
      const hasEntries = await crudSyncQueue.hasEntries(db);
      const hasIncomplete = hasEntries ? await crudSyncQueue.hasIncomplete(db) : false;

      if (hasEntries && !hasIncomplete) {
        const queueForms = await crudSyncQueue.getAllProgress(db);
        const formIds = Object.keys(queueForms);
        let hasNewData = false;

        await formIds.reduce(async (prev, fId) => {
          await prev;
          const localCount = await crudDataPoints.countSyncedByFormId(db, Number(fId));
          if (localCount !== queueForms[fId].total) {
            hasNewData = true;
          }
        }, Promise.resolve());

        if (!hasNewData) {
          await crudJobs.deleteJob(db, activeJob.id);
          DatapointSyncState.update((s) => {
            s.inProgress = false;
            s.progress = 0;
            s.syncingFormId = null;
            s.formProgress = {};
          });
          return;
        }
      }

      // Build initial formProgress from queue (for resume)
      let allProgress = await crudSyncQueue.getAllProgress(db);
      DatapointSyncState.update((s) => {
        s.formProgress = { ...allProgress };
      });

      // Calculate global totals from queue (completed forms)
      let totalCount = 0;
      let globalProcessed = 0;
      let hasErrors = false;
      Object.keys(allProgress).forEach((fId) => {
        totalCount += allProgress[fId].total;
        globalProcessed += allProgress[fId].processed;
      });

      // Process each registration form one at a time
      await registrationForms.reduce(async (previousFormPromise, regForm) => {
        await previousFormPromise;
        const { formId } = regForm;

        // Check queue for resume state
        const queueRow = await crudSyncQueue
          .getIncompleteForms(db)
          .then((rows) => rows.find((r) => r.formId === formId));

        // Resume from last incomplete page, or start from page 1 for fresh/complete forms
        const startPage = queueRow ? queueRow.lastPage + 1 : 1;

        // Signal which form is now syncing
        DatapointSyncState.update((s) => {
          s.syncingFormId = formId;
        });

        // Fresh cache for THIS form only
        const formCache = new Map();
        let formItemsProcessed = queueRow ? allProgress[formId]?.processed || 0 : 0;

        await fetchFormDatapointsPageByPage(
          formId,
          async (pageData, page, totalPage, total) => {
            // On first page response: upsert queue with actual API totals
            if (page === startPage) {
              await crudSyncQueue.upsertQueue(db, [
                {
                  formId,
                  totalPage,
                  totalData: total,
                },
              ]);

              // Update totalCount with fresh data
              if (!allProgress[formId]) {
                totalCount += total;
              } else if (allProgress[formId].total !== total) {
                totalCount += total - allProgress[formId].total;
              }

              DatapointSyncState.update((s) => {
                if (!s.formProgress[formId]) {
                  s.formProgress[formId] = { total, processed: 0 };
                }
                s.formProgress[formId].total = total;
              });
            }

            // Download each datapoint on this page
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
                  activeJob.user,
                  formCache,
                );
              } catch (error) {
                pageHasErrors = true;
                hasErrors = true;
                Sentry.captureMessage(`Error downloading datapoint JSON for URL ${item.url}`);
                Sentry.captureException(error);
              }

              formItemsProcessed += 1;
              globalProcessed += 1;

              // Update progress — capped at 100%
              DatapointSyncState.update((s) => {
                s.progress =
                  totalCount > 0 ? Math.min((globalProcessed / totalCount) * 100, 100) : 0;
                if (!s.formProgress[formId]) {
                  s.formProgress[formId] = { total: 0, processed: 0 };
                }
                s.formProgress[formId].processed = formItemsProcessed;
              });
            }, Promise.resolve());

            // Only advance page if all items succeeded — failed pages retry
            if (!pageHasErrors) {
              await crudSyncQueue.updateLastPage(db, formId, page);
            }
          },
          startPage,
          SYNC_PAGE_SIZE,
        );

        // Clear cache for this form to free memory
        formCache.clear();

        // Refresh allProgress after form completes
        allProgress = await crudSyncQueue.getAllProgress(db);

        // Refresh Home page counts after each form completes
        UIState.update((s) => {
          s.refreshPage = true;
        });
      }, Promise.resolve());

      if (!hasErrors) {
        // All forms done without errors — notify backend to update last_synced_at
        try {
          await markSyncComplete();
          // Clear queue after successful sync so next sync starts fresh
          // (backend uses last_synced_at to return only new data)
          await crudSyncQueue.clearQueue(db);
        } catch (error) {
          Sentry.captureMessage('Failed to mark sync complete on backend');
          Sentry.captureException(error);
        }
        // Done — delete job
        await crudJobs.deleteJob(db, activeJob.id);
      } else {
        // Some items failed — keep job pending for retry, queue preserves progress
        await crudJobs.updateJob(db, activeJob.id, {
          status: jobStatus.PENDING,
          attempt: activeJob.attempt + 1,
          info: 'Some datapoint downloads failed',
        });
      }

      DatapointSyncState.update((s) => {
        s.inProgress = false;
        s.progress = 0;
        s.syncingFormId = null;
        s.formProgress = {};
      });
    } catch (error) {
      // Queue persists for resume on next sync attempt
      DatapointSyncState.update((s) => {
        s.inProgress = false;
        s.progress = 0;
        s.syncingFormId = null;
        s.formProgress = {};
      });
      await crudJobs.updateJob(db, activeJob.id, {
        status: jobStatus.PENDING,
        attempt: activeJob.attempt + 1,
        info: String(error),
      });
    }
  }, [db]);

  const onSyncDraftDatapoint = useCallback(async () => {
    const allDraftSynced = await crudDataPoints.getDraftPendingSync(db);
    if (allDraftSynced?.length || (allDraftSynced?.length === 0 && isManualSynced)) {
      try {
        await crudDataPoints.deleteDraftSynced(db);
        DatapointSyncState.update((s) => {
          s.draftInProgress = true;
        });

        await fetchDraftDatapointsPageByPage(async (pageData) => {
          await pageData.reduce(async (previousPromise, draftData) => {
            await previousPromise;

            const {
              administration: administrationId,
              datapoint_name: name,
              geolocation: geo,
              form: formId,
              id: draftId,
              repeats,
              ...d
            } = draftData;

            const existingDraft = await crudDataPoints.getByDraftId(db, { draftId });

            if (existingDraft && existingDraft?.syncedAt) {
              await crudDataPoints.updateDataPoint(db, {
                ...d,
                id: existingDraft.id,
                name,
                geo,
                repeats: JSON.stringify(repeats),
                submitted: 0,
                syncedAt: new Date().toISOString(),
              });
            } else {
              const form = await crudForms.getByFormId(db, { formId });
              if (!form) {
                return;
              }

              // Drafts uploaded by versions without draftId bookkeeping can
              // only be matched by uuid — link instead of inserting a
              // duplicate; local answers stay queued and win on next upload
              const localDraft = d?.uuid
                ? await crudDataPoints.getDraftByUUID(db, { uuid: d.uuid, form: form.id })
                : null;
              if (localDraft) {
                await crudDataPoints.linkDraftId(db, localDraft.id, draftId);
                return;
              }

              const draftDatapoint = {
                ...d,
                administrationId,
                name,
                geo,
                draftId,
                repeats: JSON.stringify(repeats),
                form: form.id,
                submitted: 0,
                user: userId,
                createdAt: new Date().toISOString(),
                syncedAt: new Date().toISOString(),
              };
              await crudDataPoints.saveDataPoint(db, draftDatapoint);
            }
          }, Promise.resolve());
        });

        await crudDataPoints.deleteDraftIdIsNull(db);

        DatapointSyncState.update((s) => {
          s.draftInProgress = false;
        });
      } catch (error) {
        UIState.update((s) => {
          s.statusBar = {
            type: SYNC_STATUS.failed,
            bgColor: '#ec003f',
            icon: 'alert',
            error: String(error),
          };
        });
      }
    }
  }, [db, userId, isManualSynced]);

  const runSyncSequence = useCallback(async () => {
    if (syncLockRef.current) {
      return;
    }
    syncLockRef.current = true;

    try {
      // Prevent premature success statusBar from syncFormSubmission
      DatapointSyncState.update((s) => {
        s.inProgress = true;
      });

      // Phase 1: Upload submitted datapoints
      UIState.update((s) => {
        s.statusBar = {
          type: SYNC_STATUS.on_progress,
          bgColor: '#2563eb',
          icon: 'cloud-upload',
          syncPhase: 'uploading',
        };
      });
      try {
        await onSync();
      } catch (error) {
        Sentry.captureException(error);
      }

      // Phase 2: Sync draft datapoints
      UIState.update((s) => {
        s.statusBar = {
          type: SYNC_STATUS.on_progress,
          bgColor: '#2563eb',
          icon: 'cloud-upload',
          syncPhase: 'syncing_drafts',
        };
      });
      try {
        await onSyncDraftDatapoint();
      } catch (error) {
        Sentry.captureException(error);
      }

      // Phase 3: Download all datapoints from server
      UIState.update((s) => {
        s.statusBar = {
          type: SYNC_STATUS.on_progress,
          bgColor: '#2563eb',
          icon: 'cloud-download',
          syncPhase: 'downloading',
        };
      });
      try {
        await onSyncDataPoint();
      } catch (error) {
        Sentry.captureException(error);
      }

      // All phases complete
      UIState.update((s) => {
        s.isManualSynced = false;
        s.refreshPage = true;
        s.statusBar = {
          type: SYNC_STATUS.success,
          bgColor: '#16a34a',
          icon: 'checkmark-done',
        };
      });
    } finally {
      syncLockRef.current = false;
    }
  }, [onSync, onSyncDraftDatapoint, onSyncDataPoint]);

  useEffect(() => {
    const unsubsDataSync = DatapointSyncState.subscribe(
      (s) => s.added,
      (added) => {
        if (added) {
          runSyncSequence();
        }
      },
    );

    return () => {
      unsubsDataSync();
    };
  }, [runSyncSequence]);

  return null;
};

export default SyncService;
