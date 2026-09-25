/* eslint-disable no-console */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Icon from 'react-native-vector-icons/Ionicons';
import { BackHandler, Platform, StyleSheet, Text, ToastAndroid, TouchableOpacity, View } from 'react-native';
import { Dialog } from '@rneui/themed';
import * as Notifications from 'expo-notifications';
import * as Location from 'expo-location';
import * as Network from 'expo-network';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout } from '../components';
import {
  FormState,
  UserState,
  UIState,
  BuildParamsState,
  DatapointSyncState,
  AuthState,
} from '../store';
import useTheme from '../lib/theme';
import { crudForms, crudUsers } from '../database/crud';
import { api, cascades, i18n } from '../lib';
import useVersionCheck from '../hooks/use-version-check';
import crudJobs from '../database/crud/crud-jobs';
import {
  SYNC_DATAPOINT_JOB_NAME,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  jobStatus,
} from '../lib/constants';

const Home = ({ navigation, route }) => {
  const params = route?.params || null;
  const [search, setSearch] = useState(null);
  const [data, setData] = useState([]);
  const [appLang, setAppLang] = useState('en');
  const [loading, setloading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncDisabled, setSyncDisabled] = useState(false);

  const locationIsGranted = UserState.useState((s) => s.locationIsGranted);
  const gpsAccuracyLevel = BuildParamsState.useState((s) => s.gpsAccuracyLevel);
  const gpsInterval = BuildParamsState.useState((s) => s.gpsInterval);
  const userId = UserState.useState((s) => s.id);
  const passcode = AuthState.useState((s) => s.authenticationCode);
  const isOnline = UIState.useState((s) => s.online);
  const syncWifiOnly = UserState.useState((s) => s.syncWifiOnly);
  const refreshPage = UIState.useState((s) => s.refreshPage);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const theme = useTheme();
  const db = useSQLiteContext();

  const { id: currentUserId, name: currentUserName } = UserState.useState((s) => s);

  const {
    visible: updateDialogVisible,
    updateInfo,
    handleUpdate,
    handleSkip,
  } = useVersionCheck({ autoCheck: true });

  const goToSubmission = (id) => {
    const findForm = data.find((d) => d?.id === id);
    FormState.update((s) => {
      s.form = findForm;
    });
    navigation.push('Submission', {
      id,
      name: findForm.name,
      formId: findForm.formId,
      draft: findForm?.draft,
    });
  };

  const goToUsers = () => {
    navigation.navigate('Users');
  };
  const syncAllForms = async (myForms = [], newForms = []) => {
    try {
      await cascades.dropFiles();
      const endpoints = [...myForms, ...newForms]?.map((d) => api.get(`/form/${d.formId}`));
      const results = await Promise.allSettled(endpoints);
      const responses = results.filter(({ status }) => status === 'fulfilled');
      const cascadeFiles = responses.flatMap(({ value: res }) => res.data.cascades);
      const downloadFiles = [...new Set(cascadeFiles)];

      await downloadFiles.reduce(async (prev, file) => {
        await prev;
        await cascades.download(api.getConfig().baseURL + file, file, true);
      }, Promise.resolve());

      await responses.reduce(async (prev, { value: res }) => {
        await prev;
        const { data: apiData } = res;
        const { id: formId, version, parent: parentId } = apiData;
        const findNew = newForms.find((n) => n.id === formId);
        await crudForms.upsertForm(db, {
          ...(findNew || {}),
          id: formId,
          parentId,
          userId,
          version,
          formJSON: apiData,
        });
      }, Promise.resolve());
    } catch (error) {
      Sentry.captureMessage('[Home] Unable sync all forms');
      Sentry.captureException(error);
      Promise.reject(error);
    }
  };

  const syncUserForms = async () => {
    const { data: apiData } = await api.post('/auth?keep_last_synced_at=true', { code: passcode });
    api.setToken(apiData.syncToken);

    const myForms = await crudForms.getMyForms(db);

    if (myForms.length > apiData.formsUrl.length) {
      const formsToDelete = myForms.filter(
        (mf) => !apiData.formsUrl.map((n) => n?.id).includes(mf.formId),
      );
      await formsToDelete.reduce(async (prev, mf) => {
        await prev;
        await crudForms.deleteForm(db, mf.id);
      }, Promise.resolve());
    }

    const newForms = apiData.formsUrl
      .filter((f) => !myForms?.map((mf) => mf.formId)?.includes(f.id))
      .map((f) => ({ ...f, formId: f.id }));

    await syncAllForms(myForms, newForms);
  };

  const runSyncSubmisionManually = async () => {
    UIState.update((s) => {
      s.isManualSynced = true;
    });
  };

  const handleOnSync = async () => {
    setSyncLoading(true);
    try {
      await runSyncSubmisionManually();
      await syncUserForms();
      await crudUsers.updateLastSynced(db, userId);
      const existingDatapointJob = await crudJobs.getActiveJob(db, SYNC_DATAPOINT_JOB_NAME);
      if (!existingDatapointJob) {
        await crudJobs.addJob(db, {
          user: userId,
          type: SYNC_DATAPOINT_JOB_NAME,
          status: jobStatus.PENDING,
        });
      }
      const existingSubmissionJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
      if (!existingSubmissionJob) {
        await crudJobs.addJob(db, {
          user: userId,
          type: SYNC_FORM_SUBMISSION_TASK_NAME,
          status: jobStatus.PENDING,
        });
      }
      DatapointSyncState.update((s) => {
        s.inProgress = true;
        s.added = true;
      });
    } catch (error) {
      ToastAndroid.show(`[ERROR SYNC DATAPOINT]: ${error}`, ToastAndroid.LONG);
      Sentry.captureMessage('[Home] Unable to sync data-points');
      Sentry.captureException(error);
      setSyncLoading(false);
    }
  };

  const getUserForms = useCallback(async () => {
    /**
     * The Form List will be refreshed when:
     * - parameter change
     * - current user id exists
     * - active language change
     * - manual synced change as True
     */
    if (params || currentUserId || activeLang !== appLang || refreshPage) {
      if (activeLang !== appLang) {
        setAppLang(activeLang);
      }

      if (refreshPage) {
        UIState.update((s) => {
          s.refreshPage = false;
        });
      }

      try {
        const results = await crudForms.selectLatestFormVersion(db, { user: currentUserId });
        const forms = results
          .map((r) => ({
            ...r,
            subtitles: [
              `${trans.versionLabel}${r.version}`,
              `${trans.submittedLabel}${r.submitted}`,
              `${trans.draftLabel}${r.draft}`,
              `${trans.syncLabel}${r.synced}`,
            ],
          }))
          .filter((r) => r?.userId === currentUserId);
        setData(forms);
        setloading(false);
      } catch (error) {
        setloading(false);
        Sentry.captureMessage("[Home] Unable to refresh user's forms");
        Sentry.captureException(error);
        if (Platform.OS === 'android') {
          ToastAndroid.show(`SQL: ${error}`, ToastAndroid.SHORT);
        }
      }
    }
  }, [
    db,
    params,
    currentUserId,
    activeLang,
    appLang,
    trans.versionLabel,
    trans.submittedLabel,
    trans.draftLabel,
    trans.syncLabel,
    refreshPage,
  ]);

  useEffect(() => {
    getUserForms();
  }, [getUserForms]);

  useEffect(() => {
    if (!updateDialogVisible) {
      return () => {};
    }
    // Dismissing suppresses the prompt for 24h, so it must be a deliberate
    // press on "Later" — not a stray back press. The dialog always offers it.
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => true);
    return () => subscription.remove();
  }, [updateDialogVisible]);

  useEffect(() => {
    if (loading) {
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.downloadingData, ToastAndroid.SHORT);
      }
    }
  }, [loading, trans.downloadingData]);

  const filteredData = useMemo(
    () =>
      data.filter(
        (d) => (search && d?.name?.toLowerCase().includes(search.toLowerCase())) || !search,
      ),
    [data, search],
  );

  useEffect(() => {
    const subscription = Notifications.addNotificationReceivedListener(() => {
      getUserForms();
    });

    return () => subscription.remove();
  }, [getUserForms]);

  const watchCurrentPosition = useCallback(
    async (unsubscribe = false) => {
      if (!locationIsGranted) {
        return;
      }
      const timeInterval = gpsInterval * 1000; // miliseconds
      /**
       * Subscribe to the user's current location
       * @tutorial https://docs.expo.dev/versions/latest/sdk/location/#locationwatchpositionasyncoptions-callback
       */
      const watch = await Location.watchPositionAsync(
        {
          accuracy: gpsAccuracyLevel,
          timeInterval,
        },
        (res) => {
          UserState.update((s) => {
            s.currentLocation = res;
          });
        },
      );

      if (unsubscribe) {
        watch.remove();
      }
    },
    [gpsAccuracyLevel, gpsInterval, locationIsGranted],
  );

  useEffect(() => {
    watchCurrentPosition();
    return () => {
      watchCurrentPosition(true);
    };
  }, [watchCurrentPosition]);

  useEffect(() => {
    const unsubsDataSync = DatapointSyncState.subscribe(
      ({ inProgress, draftInProgress }) => ({ inProgress, draftInProgress }),
      ({ inProgress, draftInProgress }) => {
        if (!syncLoading && (inProgress || draftInProgress)) {
          setSyncLoading(true);
        }
        if (!inProgress && !draftInProgress) {
          setSyncLoading(false);
        }
      },
    );

    return () => {
      unsubsDataSync();
    };
  }, [syncLoading]);

  useEffect(() => {
    const unsubsNetwork = UIState.subscribe(
      (s) => s.networkType,
      (t) => {
        if (syncWifiOnly && (t !== Network.NetworkStateType.WIFI || t !== 'wifi')) {
          setSyncDisabled(true);
        }
      },
    );

    const unsubsWifi = UserState.subscribe(
      (s) => s.syncWifiOnly,
      (status) => {
        if (!status) {
          setSyncDisabled(false);
        }
      },
    );

    return () => {
      unsubsNetwork();
      unsubsWifi();
    };
  }, [syncWifiOnly]);

  useEffect(() => {
    const unsub = UIState.subscribe(
      (s) => s.triggerSync,
      (triggered) => {
        if (!triggered) {
          return;
        }
        UIState.update((s) => {
          s.triggerSync = false;
        });
        if (!syncLoading && !syncDisabled && isOnline) {
          handleOnSync();
        }
      },
    );
    return () => {
      unsub();
    };
  });

  return (
    <BaseLayout
      title={trans.homePageTitle}
      search={{
        show: true,
        placeholder: trans.homeSearch,
        value: search,
        action: setSearch,
      }}
      rightComponent={
        <TouchableOpacity
          style={[homeStyles.headerButton, { backgroundColor: theme.bg.surfaceTranslucent }]}
          onPress={goToUsers}
        >
          <Icon name="people-outline" size={18} color={theme.topNav.icon} />
        </TouchableOpacity>
      }
      leftComponent={
        <View style={homeStyles.userInfo}>
          <Icon name="person-circle-outline" size={22} color={theme.topNav.icon} />
          <Text
            style={[homeStyles.userName, { color: theme.topNav.text }]}
            numberOfLines={1}
          >
            {currentUserName || ''}
          </Text>
        </View>
      }
    >
      <BaseLayout.Content data={filteredData} action={goToSubmission} columns={1} />
      <Dialog isVisible={updateDialogVisible} onBackdropPress={() => {}}>
        <Dialog.Title title={trans.updateRequiredTitle} />
        <Text>{updateInfo.text}</Text>
        <Dialog.Actions>
          <Dialog.Button testID="update-confirm-button" onPress={handleUpdate}>
            {trans.buttonUpdate}
          </Dialog.Button>
          <Dialog.Button testID="update-skip-button" onPress={handleSkip}>
            {trans.buttonLater}
          </Dialog.Button>
        </Dialog.Actions>
      </Dialog>
    </BaseLayout>
  );
};

const homeStyles = StyleSheet.create({
  headerButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 4,
  },
  userInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingLeft: 4,
  },
  userName: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default Home;
