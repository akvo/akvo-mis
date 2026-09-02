/* eslint-disable no-console */
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Platform,
  ToastAndroid,
  BackHandler,
  ActivityIndicator,
  StyleSheet,
  View,
} from 'react-native';
import { Button, Dialog, Text } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import * as Crypto from 'expo-crypto';
import FormContainer from '../form/FormContainer';
import { SaveDialogMenu, SaveDropdownMenu } from '../form/support';
import { BaseLayout } from '../components';
import { crudDataPoints } from '../database/crud';
import { persistSubmission, refreshStorageWarning } from '../lib/submission-fallback';
import { UserState, UIState, FormState } from '../store';
import { generateDataPointName, getDurationInMinutes, transformAnswers } from '../form/lib';
import { i18n } from '../lib';
import crudJobs from '../database/crud/crud-jobs';
import { SYNC_FORM_SUBMISSION_TASK_NAME, QUESTION_TYPES, jobStatus } from '../lib/constants';

const FormPage = ({ navigation, route }) => {
  const selectedForm = FormState.useState((s) => s.form);
  const surveyDuration = FormState.useState((s) => s.surveyDuration);
  const surveyStart = FormState.useState((s) => s.surveyStart);
  const currentValues = FormState.useState((s) => s.currentValues);
  const hasUnsavedChanges = FormState.useState((s) => s.hasUnsavedChanges);
  const cascades = FormState.useState((s) => s.cascades);
  const repeats = FormState.useState((s) => s.repeats);
  const userId = UserState.useState((s) => s.id);
  const [showDialogMenu, setShowDialogMenu] = useState(false);
  const [showDropdownMenu, setShowDropdownMenu] = useState(false);
  const [showExitConfirmationDialog, setShowExitConfirmationDialog] = useState(false);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const currentFormId = route?.params?.id;
  // continue saved submission
  const savedDataPointId = route?.params?.dataPointId;
  const isNewSubmission = route?.params?.newSubmission;
  const [currentDataPoint, setCurrentDataPoint] = useState({});
  const [loading, setLoading] = useState(false);
  const db = SQLite.useSQLiteContext();
  // Stable for the life of this screen, so a retry after a failed save overwrites its
  // own fallback file instead of accumulating one per attempt.
  const submissionUuidRef = useRef(route.params?.uuid || Crypto.randomUUID());
  // Writes made by the app itself — loading a draft, clearing the form — are not
  // changes by the user. Pullstate dispatches subscriptions synchronously inside
  // update() (_updateState iterates clientSubscriptions in a plain loop), so raising
  // this before an update and lowering it after covers exactly that update.
  const suppressTrackingRef = useRef(false);

  // Runs `write` with change tracking off. Synchronous by design: an async callback
  // would leave tracking disabled while unrelated writes land.
  const withoutTracking = (write) => {
    suppressTrackingRef.current = true;
    try {
      write();
    } finally {
      suppressTrackingRef.current = false;
    }
  };

  const formJSON = useMemo(() => {
    if (!selectedForm?.json) {
      return {};
    }
    return JSON.parse(selectedForm.json);
  }, [selectedForm]);

  const refreshForm = useCallback(async () => {
    const { cascades: cascadesFiles } = formJSON || {};
    if (cascadesFiles?.length) {
      await cascadesFiles.reduce(async (prev, csFile) => {
        await prev;
        const [dbFile] = csFile?.split('/')?.slice(-1) || [];
        const connDB = await SQLite.openDatabaseAsync(dbFile, { useNewConnection: true });
        await connDB.closeAsync();
      }, Promise.resolve());
    }

    // Suppressed, and not merely for tidiness: subscribers run inside _updateState
    // after the new state is committed, so the subscription below would fire on
    // `currentValues = {}` and set hasUnsavedChanges back to true in a nested update
    // — leaving the flag raised on a form with no answers in it.
    withoutTracking(() => {
      FormState.update((s) => {
        s.surveyStart = null;
        s.currentValues = {};
        s.visitedQuestionGroup = [];
        s.cascades = {};
        s.surveyDuration = 0;
        s.repeats = {};
        s.hasUnsavedChanges = false;
      });
    });
  }, [formJSON]);

  useEffect(() => {
    // FormState is global and outlives this screen, so a flag left raised by the last
    // form would make the very first back press prompt. Reset on mount.
    FormState.update((s) => {
      s.hasUnsavedChanges = false;
    });

    // Subscribing catches every writer — fields, prefill, geo, autofield, map — and
    // any added later, which setting the flag at each call site would not. Installed
    // once: it captures nothing that changes.
    const unsubscribe = FormState.subscribe(
      (s) => s.currentValues,
      () => {
        if (suppressTrackingRef.current) {
          return;
        }
        FormState.update((s) => {
          s.hasUnsavedChanges = true;
        });
      },
    );

    return unsubscribe;
  }, []);

  // Every exit returns to the screen that opened the form — the list the user was
  // working in, which refetches and shows what just happened. Home is only a fallback
  // for a stack with nothing to go back to (restored state, a future deep link).
  const leaveForm = () => {
    // Home stays mounted below and computes its card counts once, so it has to be
    // told. This replaces navigating to Home purely to trigger that refresh.
    UIState.update((s) => {
      s.refreshPage = true;
    });
    if (navigation.canGoBack()) {
      navigation.goBack();
      return;
    }
    navigation.navigate('Home');
  };

  const handleOnPressArrowBackButton = async () => {
    if (hasUnsavedChanges) {
      setShowDialogMenu(true);
      return;
    }
    await refreshForm();
    leaveForm();
  };

  // Queues the upload job. Deliberately non-fatal: the answers are what matter, and
  // SyncService recreates a missing job on its next pass. Reported so that a job
  // insert failing systematically cannot hide behind that.
  const queueSyncJob = async (info = null) => {
    try {
      const activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
      if (activeJob) {
        return;
      }
      const infoVal = info ? { info } : {};
      await crudJobs.addJob(db, {
        user: userId,
        type: SYNC_FORM_SUBMISSION_TASK_NAME,
        status: jobStatus.PENDING,
        ...infoVal,
      });
    } catch (error) {
      Sentry.captureMessage('[FormPage] could not queue the sync job, saving anyway');
      Sentry.captureException(error);
    }
  };

  // Shared tail for both save paths. 'saved' and 'fallback' are durable, so leaving
  // the screen is safe; 'failed' means the answers exist only in the Pullstate store,
  // and navigating away would discard them.
  const finishSave = async (result, successText) => {
    if (result === 'failed') {
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.saveFailedKeepOpenText, ToastAndroid.LONG);
      }
      return;
    }
    if (Platform.OS === 'android') {
      ToastAndroid.show(
        result === 'fallback' ? trans.savedToDeviceText : successText,
        ToastAndroid.LONG,
      );
    }
    await refreshStorageWarning();
    await refreshForm();
    leaveForm();
  };

  const handleOnSaveAndExit = async ({ sendToWeb = false } = {}) => {
    await queueSyncJob();
    const { dpName, dpGeo } = generateDataPointName(formJSON, currentValues, cascades);
    const jsonAnswers = transformAnswers(currentValues, formJSON);
    try {
      const saveData = {
        form: currentFormId,
        user: userId,
        name: dpName || trans.untitled,
        submitted: 0,
        duration: surveyDuration,
        json: jsonAnswers,
        uuid: submissionUuidRef.current,
        geo: dpGeo,
        // A draft save is a deliberate overwrite, so each save mints a fresh
        // key. Only an unintended replay reuses one.
        submissionKey: Crypto.randomUUID(),
      };

      const duration = getDurationInMinutes(surveyStart) + surveyDuration;
      const payload = {
        ...currentDataPoint,
        ...saveData,
        duration: duration === 0 ? 1 : duration,
        repeats: Object.keys(repeats).length ? JSON.stringify(repeats) : null,
        syncedAt: null,
        ...(isNewSubmission ? { locallyCreated: 1 } : {}),
        ...(sendToWeb ? { sendToWeb: 1 } : {}),
      };
      const result = await persistSubmission(db, payload, isNewSubmission);
      await finishSave(result, trans.successSaveDatapoint);
    } catch (error) {
      Sentry.captureMessage('[FormPage] Cannot save draft submissions');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.saveFailedKeepOpenText, ToastAndroid.LONG);
      }
    }
  };

  const handleShowExitConfirmationDialog = () => {
    setShowDropdownMenu(false);
    setShowDialogMenu(false);
    setShowExitConfirmationDialog(true);
  };

  const handleOnExit = async () => {
    await refreshForm();
    return leaveForm();
  };

  const handleOnSubmitForm = async (values) => {
    try {
      const answers = transformAnswers(values.answers, formJSON);

      const datapoitName = values?.name || trans.untitled;
      const submitData = {
        form: currentFormId,
        user: userId,
        name: datapoitName,
        geo: values.geo,
        submitted: 1,
        duration: surveyDuration,
        json: answers,
        uuid: submissionUuidRef.current,
        locallyCreated: 1,
        // Minted once here and resent unchanged on every retry. saveAsPending
        // clears syncedAt but never this, which is what makes a retry a replay
        // rather than a second submission.
        submissionKey: Crypto.randomUUID(),
      };
      const duration = getDurationInMinutes(surveyStart) + surveyDuration;
      const payload = {
        ...currentDataPoint,
        ...submitData,
        duration: duration === 0 ? 1 : duration,
        syncedAt: null,
      };
      const result = await persistSubmission(db, payload, isNewSubmission);
      if (result !== 'failed') {
        /**
         * Create a new job for syncing form submissions.
         */
        await queueSyncJob(route.params?.uuid);
      }
      await finishSave(result, trans.successSubmitted);
    } catch (error) {
      Sentry.captureMessage('[FormPage] Cannot submit submissions');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.saveFailedKeepOpenText, ToastAndroid.LONG);
      }
    }
  };

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (hasUnsavedChanges) {
        setShowDialogMenu(true);
        return true;
      }
      refreshForm();
      return false;
    });
    return () => backHandler.remove();
  }, [hasUnsavedChanges, refreshForm]);

  const fetchSavedSubmission = useCallback(async () => {
    if (!savedDataPointId) {
      return;
    }
    setLoading(true);
    const dpValue = await crudDataPoints.selectDataPointById(db, { id: savedDataPointId });
    setCurrentDataPoint(dpValue);
    const jsonData = dpValue?.json;
    if (jsonData && Object.keys(jsonData).length) {
      let prevAdmAnswer = [];
      // Process cascade questions
      (formJSON?.question_group || [])
        .flatMap((qg) => qg.question)
        .filter((q) => q.type === QUESTION_TYPES.cascade)
        .forEach((q) => {
          const val = jsonData[q.id];
          if (q?.source?.file === 'administrator.sqlite' && val) {
            prevAdmAnswer = Array.isArray(val) ? val : [val];
          }
          if (val && !Array.isArray(val)) {
            jsonData[q.id] = [val];
          }
        });
      // The stored answers arriving in state is not the user changing them.
      withoutTracking(() => {
        FormState.update((s) => {
          s.currentValues = jsonData;
          s.prevAdmAnswer = prevAdmAnswer;
        });
      });
    }
    setLoading(false);
  }, [db, savedDataPointId, formJSON]);

  useEffect(() => {
    fetchSavedSubmission();
  }, [fetchSavedSubmission]);

  return (
    <BaseLayout
      title={route?.params?.name}
      subTitle="formPage"
      leftComponent={
        <Button type="clear" onPress={handleOnPressArrowBackButton} testID="arrow-back-button">
          <Icon name="arrow-back" size={18} />
        </Button>
      }
      rightComponent={
        <SaveDropdownMenu
          visible={showDropdownMenu}
          setVisible={setShowDropdownMenu}
          anchor={
            <Button
              type="clear"
              testID="form-page-kebab-menu"
              onPress={() => setShowDropdownMenu(true)}
            >
              <Icon name="ellipsis-vertical" size={18} />
            </Button>
          }
          handleOnExit={handleShowExitConfirmationDialog}
          handleOnSaveAndExit={handleOnSaveAndExit}
        />
      }
    >
      {!loading ? (
        <FormContainer
          forms={formJSON}
          onSubmit={handleOnSubmitForm}
          setShowDialogMenu={setShowDialogMenu}
          db={db}
          isNewSubmission={isNewSubmission}
        />
      ) : (
        <View style={styles.loadingContainer}>
          <ActivityIndicator />
        </View>
      )}
      <SaveDialogMenu
        visible={showDialogMenu}
        setVisible={setShowDialogMenu}
        handleOnExit={handleShowExitConfirmationDialog}
        handleOnSaveAndExit={handleOnSaveAndExit}
      />
      <Dialog visible={showExitConfirmationDialog} testID="exit-confirmation-dialog">
        <Text testID="exit-confirmation-text">{trans.confirmExit}</Text>
        <Dialog.Actions>
          <Dialog.Button
            title={trans.buttonExit}
            onPress={handleOnExit}
            testID="exit-confirmation-ok"
          />
          <Dialog.Button
            title={trans.buttonCancel}
            onPress={() => setShowExitConfirmationDialog(false)}
            testID="exit-confirmation-cancel"
          />
        </Dialog.Actions>
      </Dialog>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    flexDirection: 'column',
    justifyContent: 'center',
  },
});

export default FormPage;
