import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  ToastAndroid,
  PermissionsAndroid,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useSQLiteContext } from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import { FormState, UIState, BuildParamsState } from '../../store';
import { helpers, i18n } from '../../lib';
import { compressImage, persistImage } from '../../lib/image-compressor';
import { crudDataPoints } from '../../database/crud';
import {
  BaseLayout,
  ImageView,
  AttachmentView,
  SubtitleContent,
  formDataDetailsStyles as sharedStyles,
} from '../../components';
import FormDataNavigation from './FormDataNavigation';
import { QUESTION_TYPES } from '../../lib/constants';
import MIME_TYPES from '../../lib/mime_types';

const FormDataDetails = ({ navigation, route }) => {
  const selectedForm = FormState.useState((s) => s.form);
  const currentValues = FormState.useState((s) => s.currentValues);
  const [currentPage, setCurrentPage] = useState(0);
  const [retakingKey, setRetakingKey] = useState(null);
  const activeLang = UIState.useState((s) => s.lang);
  const imageQuality = BuildParamsState.useState((s) => s.imageQuality);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const datapointId = route?.params?.id;
  // Retake only repairs local rows still waiting to upload
  const canRetake = !!datapointId && !route?.params?.isSynced;

  const ensureCameraPermission = async () => {
    const isGranted = await PermissionsAndroid.check(PermissionsAndroid.PERMISSIONS.CAMERA);
    if (isGranted) {
      return true;
    }
    const askPermission = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.CAMERA, {
      title: trans.imageStoragePerm,
      message: trans.imageCameraPerm,
      buttonNeutral: trans.imageAskLater,
      buttonNegative: trans.buttonCancel,
      buttonPositive: trans.buttonOk,
    });
    return askPermission === PermissionsAndroid.RESULTS.GRANTED;
  };

  // Shared tail for both repair paths — camera and gallery differ only in the
  // picker call that produces imageUri.
  const savePhoto = async (questionKey, imageUri) => {
    setRetakingKey(questionKey);
    try {
      let newUri = imageUri;
      try {
        const compressed = await compressImage(imageUri, imageQuality);
        newUri = compressed.uri;
      } catch (error) {
        Sentry.captureMessage(`Image compression failed for ${imageUri}`);
        Sentry.captureException(error);
      }
      // Move out of the purgeable cache dir so the photo survives until synced
      newUri = await persistImage(newUri);
      const updatedValues = { ...currentValues, [questionKey]: newUri };
      FormState.update((s) => {
        s.currentValues = updatedValues;
      });
      await crudDataPoints.updateJson(db, datapointId, updatedValues);
      // The Submission list caches its rows and only refetches on mount or on
      // refreshPage. Without this it keeps showing the File missing badge, and
      // re-opening this screen reseeds currentValues from the stale row.
      UIState.update((s) => {
        s.refreshPage = true;
      });
      ToastAndroid.show(trans.retakeSuccess, ToastAndroid.LONG);
    } finally {
      setRetakingKey(null);
    }
  };

  const handleRetake = async (questionKey) => {
    const allowed = await ensureCameraPermission();
    if (!allowed) {
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ base64: true });
    if (result?.canceled) {
      return;
    }
    await savePhoto(questionKey, result.assets[0].uri);
  };

  /**
   * No permission request is necessary for launching the image library.
   * docs: https://docs.expo.dev/versions/latest/sdk/imagepicker/#usage
   */
  const handlePickFromGallery = async (questionKey) => {
    const result = await ImagePicker.launchImageLibraryAsync({ base64: true });
    if (result?.canceled) {
      return;
    }
    await savePhoto(questionKey, result.assets[0].uri);
  };

  const handleReattach = async (questionKey, rule = null) => {
    const { allowedFileTypes } = rule || {};
    const fileTypes = allowedFileTypes?.length
      ? allowedFileTypes.map((t) => MIME_TYPES?.[t] || 'application/octet-stream')
      : '*/*';
    const result = await DocumentPicker.getDocumentAsync({
      multiple: false,
      type: fileTypes,
      copyToCacheDirectory: true,
    });
    if (result?.canceled || !result?.assets?.length) {
      return;
    }
    setRetakingKey(questionKey);
    try {
      // Move out of the purgeable cache dir so the file survives until synced
      const newUri = await persistImage(result.assets[0].uri, 'attachments');
      const updatedValues = { ...currentValues, [questionKey]: newUri };
      FormState.update((s) => {
        s.currentValues = updatedValues;
      });
      await crudDataPoints.updateJson(db, datapointId, updatedValues);
      UIState.update((s) => {
        s.refreshPage = true;
      });
      ToastAndroid.show(trans.reattachSuccess, ToastAndroid.LONG);
    } finally {
      setRetakingKey(null);
    }
  };

  const { json: formJSON } = selectedForm || {};

  const form = formJSON ? JSON.parse(formJSON) : {};
  // Skip question groups without any answered question — repeat-suffixed
  // keys (qid-1, qid-2, ...) count for their base question id
  const answeredQuestionIds = new Set(
    Object.entries(currentValues)
      .filter(
        ([, value]) => value != null && value !== '' && !(Array.isArray(value) && !value.length),
      )
      .map(([key]) => key.split('-')[0]),
  );
  const questionGroups = (form?.question_group || []).filter((qg) =>
    qg?.question?.some((q) => answeredQuestionIds.has(`${q.id}`)),
  );
  const currentGroup = questionGroups[currentPage] || [];
  const totalPage = questionGroups.length || 0;
  const questions = currentGroup?.question || [];
  const numberOfRepeat =
    Object.entries(currentValues).filter(([key]) => {
      const [questionID] = key.split('-');
      return questionID === `${questions?.[0]?.id}`;
    }).length || 1;

  // Create sections data for SectionList
  const sections = Array.from({ length: numberOfRepeat }, (_, i) => ({
    repeatIndex: i,
    title: currentGroup?.repeatable
      ? `${currentGroup?.label || currentGroup?.name} #${i + 1}`
      : currentGroup?.label || currentGroup?.name,
    data: questions.map((q, qx) => ({
      ...q,
      id: i === 0 ? q.id : `${q.id}-${i}`,
      keyform: `${i + 1}.${qx + 1}`,
      answer: currentValues?.[i === 0 ? q.id : `${q.id}-${i}`],
    })),
  }));

  const renderItem = ({ item: q, index: qIndex }) => {
    const { label, type, source, option, answer } = q;

    if (q.type === QUESTION_TYPES.attachment && answer) {
      const fileName = answer.split('/').pop();
      const fileExtension = fileName.split('.').pop();
      if (helpers.isImageFile(fileExtension)) {
        return (
          // Keyed on the question alone: ImageView derives its error state from
          // the uri, so a replacement file updates it in place instead of
          // remounting and re-running the load from scratch.
          <ImageView
            key={q.id}
            label={q.label}
            uri={answer}
            textTestID={`text-question-${qIndex}`}
            imageTestID={`image-question-${qIndex}`}
            missingText={trans.attachmentMissingText}
            retakeLabel={trans.buttonReattachFile}
            loadFailedText={trans.photoLoadFailedText}
            tryAgainLabel={trans.buttonTryAgain}
            onRetake={canRetake ? () => handleReattach(q.id, q.rule) : null}
            isRetaking={retakingKey === q.id}
            processingLabel={trans.compressingImage}
          />
        );
      }
      return (
        <AttachmentView
          key={q.id}
          label={q.label}
          uri={answer}
          index={qIndex}
          missingText={trans.attachmentMissingText}
          reattachLabel={trans.buttonReattachFile}
          openLabel={trans.openFileButton}
          onReattach={canRetake ? () => handleReattach(q.id, q.rule) : null}
          isReattaching={retakingKey === q.id}
          processingLabel={trans.compressingImage}
        />
      );
    }
    if ([QUESTION_TYPES.image, QUESTION_TYPES.signature].includes(q.type) && answer) {
      // Signatures are excluded from both repair paths: replacing one with an
      // arbitrary picked image would weaken what it attests to.
      const isPhoto = canRetake && q.type === QUESTION_TYPES.image;
      return (
        <ImageView
          key={q.id}
          label={q.label}
          uri={answer}
          textTestID={`text-question-${qIndex}`}
          imageTestID={`image-question-${qIndex}`}
          missingText={trans.fileMissingText}
          retakeLabel={trans.buttonRetakePhoto}
          galleryLabel={trans.buttonFromGallery}
          loadFailedText={trans.photoLoadFailedText}
          tryAgainLabel={trans.buttonTryAgain}
          onRetake={isPhoto ? () => handleRetake(q.id) : null}
          onPickGallery={isPhoto ? () => handlePickFromGallery(q.id) : null}
          isRetaking={retakingKey === q.id}
          processingLabel={trans.compressingImage}
        />
      );
    }
    return (
      <View key={q.keyform} style={sharedStyles.listItem}>
        <View style={sharedStyles.listItemContent}>
          <Text style={sharedStyles.listItemTitle} testID={`text-question-${qIndex}`}>
            {label}
          </Text>
          <SubtitleContent
            index={qIndex}
            answer={answer}
            type={type}
            source={source}
            option={option}
          />
        </View>
      </View>
    );
  };

  const renderSectionHeader = ({ section }) => (
    <Text style={styles.sectionTitle}>{section.title}</Text>
  );

  useEffect(
    () =>
      navigation.addListener('beforeRemove', (e) => {
        // Prevent default behavior of leaving the screen
        e.preventDefault();

        if (Object.keys(currentValues).length) {
          FormState.update((s) => {
            s.currentValues = {};
          });
          navigation.dispatch(e.data.action);
        }
      }),
    [navigation, currentValues],
  );

  return (
    <BaseLayout title={route?.params?.name} rightComponent={false}>
      <View style={styles.listContainer}>
        <SectionList
          sections={sections}
          renderItem={renderItem}
          renderSectionHeader={renderSectionHeader}
          keyExtractor={(item) => item.keyform}
          contentContainerStyle={styles.sectionList}
        />
      </View>
      <FormDataNavigation
        totalPage={totalPage}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
      />
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  sectionTitle: {
    fontWeight: '700',
    fontSize: 14,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: '#f2f2f2',
  },
  listContainer: {
    width: '100%',
    flex: 1,
  },
  sectionList: {
    flexGrow: 1,
  },
});

export default FormDataDetails;
