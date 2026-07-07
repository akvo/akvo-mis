import React, { Suspense, useCallback, useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import NetInfo from '@react-native-community/netinfo';
import * as Notifications from 'expo-notifications';
import * as TaskManager from 'expo-task-manager';
import * as BackgroundTask from 'expo-background-task';
import * as Sentry from '@sentry/react-native';
import * as Location from 'expo-location';
import { SENTRY_DSN, SENTRY_ENV } from '@env';
import { SQLiteProvider } from 'expo-sqlite';

import Navigation, { reactNavigationIntegration } from './src/navigation';
import { UIState, AuthState, UserState, BuildParamsState } from './src/store';
import { crudUsers, crudConfig, crudDataPoints } from './src/database/crud';
import { api } from './src/lib';
import { NetworkStatusBar, SyncService } from './src/components';
import backgroundTask, {
  defineSyncFormVersionTask,
  defineSyncDatapointBackgroundTask,
} from './src/lib/background-task';
import crudJobs from './src/database/crud/crud-jobs';
import {
  SYNC_DATAPOINT_BACKGROUND_TASK_NAME,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
  DATABASE_NAME,
  DATABASE_VERSION,
  MAX_ATTEMPT,
  jobStatus,
} from './src/lib/constants';
import { tables, openDatabase } from './src/database';
import sql from './src/database/sql';
import { m03, m04, m05, m06 } from './src/database/migrations';

export const setNotificationHandler = () =>
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });

setNotificationHandler();
defineSyncFormVersionTask();
defineSyncDatapointBackgroundTask();

TaskManager.defineTask(SYNC_FORM_SUBMISSION_TASK_NAME, async () => {
  try {
    const db = await openDatabase();
    const pendingToSync = await crudDataPoints.selectSubmissionToSync(db);
    const activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);

    if (activeJob?.status === jobStatus.ON_PROGRESS) {
      if (activeJob.attempt < MAX_ATTEMPT && pendingToSync.length) {
        /**
         * Job is still in progress,
         * but we still have pending items; then increase the attempt value.
         */
        await crudJobs.updateJob(db, activeJob.id, {
          attempt: activeJob.attempt + 1,
        });
      }

      if (activeJob.attempt === MAX_ATTEMPT) {
        /**
         * If the status is still IN PROGRESS and has reached the maximum attempts,
         * set it to PENDING when there are still pending sync items,
         * delete the job when it's finish and there are no pending items.
         */

        if (pendingToSync.length) {
          await crudJobs.updateJob(db, activeJob.id, {
            status: jobStatus.PENDING,
            attempt: 0, // RESET attempt to 0
          });
        } else {
          await crudJobs.deleteJob(db, activeJob.id);
        }
      }
    }

    if (
      activeJob?.status === jobStatus.PENDING ||
      (activeJob?.status === jobStatus.FAILED && activeJob?.attempt <= MAX_ATTEMPT)
    ) {
      await crudJobs.updateJob(db, activeJob.id, {
        status: jobStatus.ON_PROGRESS,
      });
      await backgroundTask.syncFormSubmission(db, activeJob);
    }
    await db.closeAsync();
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch (err) {
    Sentry.captureMessage(`[${SYNC_FORM_SUBMISSION_TASK_NAME}] Define task manager failed`);
    Sentry.captureException(err);
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

Sentry.init({
  dsn: SENTRY_DSN,
  // Set tracesSampleRate to 1.0 to capture 100%
  // of transactions for performance monitoring.
  // We recommend adjusting this value in production
  tracesSampleRate: 1.0,
  enableInExpoDevelopment: true,
  // If `true`, Sentry will try to print out useful debugging information if something goes wrong with sending the event.
  // Set it to `false` in production
  environment: SENTRY_ENV,
  debug: false,
  enableAppStartTracking: true,
  enableNativeFramesTracking: true,
  enableStallTracking: true,
  enableUserInteractionTracing: true,
  integrations: [reactNavigationIntegration],
});

const App = () => {
  const serverURLState = BuildParamsState.useState((s) => s.serverURL);
  const syncValue = BuildParamsState.useState((s) => s.dataSyncInterval);
  const gpsThreshold = BuildParamsState.useState((s) => s.gpsThreshold);
  const gpsAccuracyLevel = BuildParamsState.useState((s) => s.gpsAccuracyLevel);
  const geoLocationTimeout = BuildParamsState.useState((s) => s.geoLocationTimeout);
  const imageQuality = BuildParamsState.useState((s) => s.imageQuality);
  const appVersion = BuildParamsState.useState((s) => s.appVersion);
  const locationIsGranted = UserState.useState((s) => s.locationIsGranted);

  const handleInitConfig = async (db) => {
    const configExist = await crudConfig.getConfig(db);
    const serverURL = configExist?.serverURL || serverURLState;
    const syncInterval = configExist?.syncInterval || syncValue;
    if (!configExist) {
      await crudConfig.addConfig(db, {
        appVersion,
        serverURL,
        syncInterval,
        gpsThreshold,
        gpsAccuracyLevel,
        geoLocationTimeout,
        imageQuality,
      });
    }
    if (serverURL) {
      BuildParamsState.update((s) => {
        s.serverURL = serverURL;
      });
      api.setServerURL(serverURL);
    }
    if (configExist) {
      /**
       * Update settings values from database
       */
      BuildParamsState.update((s) => {
        s.dataSyncInterval = configExist.syncInterval;
        s.gpsThreshold = configExist.gpsThreshold;
        s.gpsAccuracyLevel = configExist.gpsAccuracyLevel;
        s.geoLocationTimeout = configExist.geoLocationTimeout;
        s.imageQuality = configExist.imageQuality || 'low';
      });

      UserState.update((s) => {
        s.syncWifiOnly = configExist?.syncWifiOnly;
      });
    }
  };

  const handleCheckSession = async (db) => {
    // check users exist
    const user = await crudUsers.getActiveUser(db);
    if (!user) {
      UIState.update((s) => {
        s.currentPage = 'GetStarted';
      });
      return;
    }
    if (user.token) {
      api.setToken(user.token);
      UserState.update((s) => {
        s.id = user.id;
        s.name = user.name;
        s.password = user.password;
      });
      AuthState.update((s) => {
        s.token = user.token;
        s.authenticationCode = user.password;
      });
      UIState.update((s) => {
        s.currentPage = 'Home';
      });
    }
  };

  const migrateDbIfNeeded = async (db) => {
    // Connection-level pragma: wait up to 5s for a concurrent writer instead of
    // failing immediately with "database is locked" (SQLITE_BUSY).
    await db.execAsync('PRAGMA busy_timeout = 5000;');
    let { user_version: currentDbVersion } = await db.getFirstAsync('PRAGMA user_version');
    if (currentDbVersion >= DATABASE_VERSION) {
      await handleInitConfig(db);
      await handleCheckSession(db);
      return;
    }

    // WAL mode must be set outside a transaction — it is a connection-level pragma.
    // user_version = 1 is set immediately after so a crash here is safely retried.
    if (currentDbVersion === 0) {
      await db.execAsync(`PRAGMA journal_mode = 'wal';`);
      await db.execAsync('PRAGMA user_version = 1');
      currentDbVersion = 1;
    }

    // Each subsequent step is wrapped in a transaction that sets user_version atomically.
    // If the migration throws, the transaction rolls back and user_version stays at the
    // previous value, so the same step is retried on next launch. Every migration's up()
    // function must be idempotent (addNewColumn / createTable already check for existence).
    if (currentDbVersion === 1) {
      await sql.withTransaction(db, async (txDb) => {
        await tables.reduce(async (prev, t) => {
          await prev;
          await sql.createTable(txDb, t.name, t.fields);
        }, Promise.resolve());
        await txDb.execAsync('PRAGMA user_version = 2');
      });
      currentDbVersion = 2;
    }
    if (currentDbVersion === 2) {
      await sql.withTransaction(db, async (txDb) => {
        await m03.up(txDb);
        await txDb.execAsync('PRAGMA user_version = 3');
      });
      currentDbVersion = 3;
    }
    if (currentDbVersion === 3) {
      await sql.withTransaction(db, async (txDb) => {
        await m04.up(txDb);
        await txDb.execAsync('PRAGMA user_version = 4');
      });
      currentDbVersion = 4;
    }
    if (currentDbVersion === 4) {
      await sql.withTransaction(db, async (txDb) => {
        await m05.up(txDb);
        await txDb.execAsync('PRAGMA user_version = 5');
      });
      currentDbVersion = 5;
    }
    if (currentDbVersion === 5) {
      await sql.withTransaction(db, async (txDb) => {
        await m06.up(txDb);
        await txDb.execAsync('PRAGMA user_version = 6');
      });
      currentDbVersion = 6;
    }
  };

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      UIState.update((s) => {
        s.online = state.isConnected;
        s.networkType = state.type?.toUpperCase();
      });
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const handleOnRegisterTask = useCallback(async () => {
    try {
      const allTasks = await TaskManager.getRegisteredTasksAsync();

      allTasks.forEach(async (a) => {
        if (
          [
            SYNC_FORM_SUBMISSION_TASK_NAME,
            SYNC_FORM_VERSION_TASK_NAME,
            SYNC_DATAPOINT_BACKGROUND_TASK_NAME,
          ].includes(a.taskName)
        ) {
          await backgroundTask.registerBackgroundTask(a.taskName);
        }
      });
    } catch (error) {
      Sentry.captureMessage(`handleOnRegisterTask`);
      Sentry.captureException(error);
    }
  }, []);

  useEffect(() => {
    handleOnRegisterTask();
  }, [handleOnRegisterTask]);

  const requestAccessLocation = useCallback(async () => {
    if (locationIsGranted) {
      return;
    }
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status === 'granted') {
      UserState.update((s) => {
        s.locationIsGranted = true;
      });
    }
  }, [locationIsGranted]);

  useEffect(() => {
    requestAccessLocation();
  }, [requestAccessLocation]);

  return (
    <SafeAreaProvider>
      <Suspense fallback={null}>
        <SQLiteProvider databaseName={DATABASE_NAME} onInit={migrateDbIfNeeded}>
          <Navigation />
          <NetworkStatusBar />
          <SyncService />
        </SQLiteProvider>
      </Suspense>
    </SafeAreaProvider>
  );
};

export default Sentry.wrap(App);
