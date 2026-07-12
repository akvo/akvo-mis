/* eslint-disable no-console */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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

    FormState.update((s) => {
      s.surveyStart = null;
      s.currentValues = {};
      s.visitedQuestionGroup = [];
      s.cascades = {};
      s.surveyDuration = 0;
      s.repeats = {};
    });
  }, [formJSON]);

  const handleOnPressArrowBackButton = async () => {
    if (Object.keys(currentValues).length) {
      setShowDialogMenu(true);
      return;
    }
    await refreshForm();
    navigation.goBack();
  };

  const handleOnSaveAndExit = async () => {
    const activeJob = await crudJobs.getActiveJob(db, SYNC_FORM_SUBMISSION_TASK_NAME);
    if (!activeJob) {
      await crudJobs.addJob(db, {
        user: userId,
        type: SYNC_FORM_SUBMISSION_TASK_NAME,
        status: jobStatus.PENDING,
      });
    }
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
        uuid: route.params?.uuid || Crypto.randomUUID(),
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
      };
      if (isNewSubmission) {
        await crudDataPoints.saveDataPoint(db, { ...payload, locallyCreated: 1 });
      } else {
        await crudDataPoints.updateDataPoint(db, payload);
      }
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.successSaveDatapoint, ToastAndroid.LONG);
      }
      await refreshForm();
      navigation.navigate('Home', { ...route?.params });
    } catch (error) {
      Sentry.captureMessage('[FormPage] Cannot save draft submissions');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(`SQL: ${error}`, ToastAndroid.LONG);
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
    return navigation.navigate('Home');
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
        uuid: route.params?.uuid || Crypto.randomUUID(),
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
      if (isNewSubmission) {
        await crudDataPoints.saveDataPoint(db, payload);
      } else {
        await crudDataPoints.updateDataPoint(db, payload);
      }
      /**
       * Create a new job for syncing form submissions.
       */
      await crudJobs.addJob(db, {
        user: userId,
        type: SYNC_FORM_SUBMISSION_TASK_NAME,
        status: jobStatus.PENDING,
        info: route.params?.uuid,
      });

      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.successSubmitted, ToastAndroid.LONG);
      }
      await refreshForm();
      navigation.navigate('Home', { ...route?.params });
    } catch (error) {
      Sentry.captureMessage('[FormPage] Cannot submit submissions');
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(`SQL: ${error}`, ToastAndroid.LONG);
      }
    }
  };

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (Object.keys(currentValues).length) {
        setShowDialogMenu(true);
        return true;
      }
      refreshForm();
      return false;
    });
    return () => backHandler.remove();
  }, [currentValues, refreshForm]);

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
      FormState.update((s) => {
        s.currentValues = jsonData;
        s.prevAdmAnswer = prevAdmAnswer;
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
