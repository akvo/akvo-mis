import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  SectionList,
  ToastAndroid,
  PermissionsAndroid,
  ActivityIndicator,
} from 'react-native';
import { Image, Button } from '@rneui/themed';
import moment from 'moment';
import * as Linking from 'expo-linking';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { useSQLiteContext } from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';
import { FormState, UIState, BuildParamsState } from '../../store';
import { api, cascades, helpers, i18n } from '../../lib';
import { compressImage, persistImage } from '../../lib/image-compressor';
import { crudDataPoints } from '../../database/crud';
import { BaseLayout } from '../../components';
import FormDataNavigation from './FormDataNavigation';
import { QUESTION_TYPES } from '../../lib/constants';
import MIME_TYPES from '../../lib/mime_types';

const ImageView = ({
  label,
  uri,
  textTestID,
  imageTestID,
  onRetake = null,
  missingText = '',
  retakeLabel = '',
  isRetaking = false,
  processingLabel = '',
}) => {
  // No upfront file check: the Image load itself reports a dead file:// path
  // via onError, so missing files cost no extra I/O.
  const [fileMissing, setFileMissing] = useState(false);
  // get base path from http://example.com/api/v2/any/ to http://example.com
  const baseURL = api.getConfig().baseURL?.replace(/\/api\/v\d+\/.*$/, '');
  const imageURL =
    !uri?.includes('file://') && !uri?.startsWith('http') && !uri.startsWith('data:image')
      ? `${baseURL}${uri}`
      : uri;
  // Retake only makes sense for local files pending upload, not remote images
  const showRetake = !!onRetake && !!uri?.startsWith('file://');

  let content = (
    <Image
      source={{ uri: imageURL }}
      testID={imageTestID}
      style={styles.image}
      onError={() => setFileMissing(true)}
    />
  );
  if (fileMissing) {
    content = (
      <View>
        <Text style={styles.missingText} testID={`${imageTestID}-missing`}>
          {missingText}
        </Text>
        {showRetake && (
          <Button title={retakeLabel} onPress={onRetake} testID={`${imageTestID}-retake`} />
        )}
      </View>
    );
  }
  if (isRetaking) {
    content = (
      <View style={styles.processingContainer} testID={`${imageTestID}-processing`}>
        <ActivityIndicator size="small" color="dodgerblue" />
        <Text style={styles.processingText}>{processingLabel}</Text>
      </View>
    );
  }

  return (
    <View style={styles.containerImage}>
      <Text style={styles.title} testID={textTestID}>
        {label}
      </Text>
      {content}
    </View>
  );
};

const AttachmentView = ({
  label,
  uri,
  index,
  onReattach = null,
  missingText = '',
  reattachLabel = '',
  openLabel = '',
  isReattaching = false,
  processingLabel = '',
}) => {
  // Non-image files render no Image, so there is no onError signal — an
  // explicit existence check is the only way (one call per attachment).
  const [fileMissing, setFileMissing] = useState(false);

  useEffect(() => {
    let active = true;
    if (uri?.startsWith('file://')) {
      FileSystem.getInfoAsync(uri)
        .then(({ exists }) => {
          if (active) {
            setFileMissing(!exists);
          }
        })
        .catch(() => {
          if (active) {
            setFileMissing(true);
          }
        });
    } else {
      setFileMissing(false);
    }
    return () => {
      active = false;
    };
  }, [uri]);

  const openFileManager = async () => {
    const supported = await Linking.canOpenURL(uri);
    if (supported) {
      await Linking.openURL(uri);
    } else {
      Alert.alert("Don't know how to open this URL:", uri);
    }
  };

  let content = (
    <View style={{ width: '100%' }}>
      <Text
        testID={`text-answer-${index}`}
        style={{ color: 'blue', textDecorationLine: 'underline' }}
      >
        {uri.split('/').pop()}
      </Text>
      <Button
        title={openLabel}
        onPress={openFileManager}
        testID={`open-file-button-${index}`}
        buttonStyle={{ width: '100%', backgroundColor: '#1E90FF', marginTop: 8 }}
      />
    </View>
  );
  if (fileMissing) {
    content = (
      <View>
        <Text style={styles.missingText} testID={`attachment-missing-${index}`}>
          {missingText}
        </Text>
        {!!onReattach && !!uri?.startsWith('file://') && (
          <Button
            title={reattachLabel}
            onPress={onReattach}
            testID={`attachment-reattach-${index}`}
          />
        )}
      </View>
    );
  }
  if (isReattaching) {
    content = (
      <View style={styles.processingContainer} testID={`attachment-processing-${index}`}>
        <ActivityIndicator size="small" color="dodgerblue" />
        <Text style={styles.processingText}>{processingLabel}</Text>
      </View>
    );
  }

  return (
    <View style={styles.listItem}>
      <View style={styles.listItemContent}>
        <Text style={styles.listItemTitle} testID={`text-question-${index}`}>
          {label}
        </Text>
        {content}
      </View>
    </View>
  );
};

const SubtitleContent = ({ index, answer, type, source = null, option = [] }) => {
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const [cascadeValue, setCascadeValue] = useState(null);

  const openFileManager = async (uri) => {
    const supported = await Linking.canOpenURL(uri);
    if (supported) {
      await Linking.openURL(uri);
    } else {
      Alert.alert("Don't know how to open this URL:", uri);
    }
  };

  const fetchCascade = useCallback(async () => {
    const cascadeID = parseInt(answer, 10);
    if (!cascadeID) {
      return;
    }
    if (source?.file) {
      const csValue = await cascades.loadDataSource(source, cascadeID);
      setCascadeValue(csValue);
    }
  }, [answer, source]);

  useEffect(() => {
    fetchCascade();
  }, [fetchCascade]);

  switch (type) {
    case QUESTION_TYPES.geo:
      return (
        <View testID={`text-type-geo-${index}`}>
          <Text>
            {trans.latitude}: {answer?.[0]}
          </Text>
          <Text>
            {trans.longitude}: {answer?.[1]}
          </Text>
        </View>
      );
    case QUESTION_TYPES.cascade:
      return <Text testID={`text-answer-${index}`}>{cascadeValue?.full_path_name || answer}</Text>;
    case QUESTION_TYPES.date:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer ? moment(answer).format('YYYY-MM-DD') : '-'}
        </Text>
      );
    case QUESTION_TYPES.option:
    case QUESTION_TYPES.multiple_option:
      return (
        <Text testID={`text-answer-${index}`}>
          {answer
            ?.map((a) => {
              const findOption = option?.find((o) => o?.value === a);
              return findOption?.label;
            })
            ?.join(', ')}
        </Text>
      );
    case QUESTION_TYPES.attachment:
      if (!answer) {
        return <Text testID={`text-type-attachment-${index}`}>-</Text>;
      }
      return (
        <View testID={`text-type-attachment-${index}`} style={{ width: '100%' }}>
          <Text
            testID={`text-answer-${index}`}
            style={{ color: 'blue', textDecorationLine: 'underline' }}
          >
            {answer.split('/').pop()}
          </Text>
          <Button
            title={trans.openFileButton}
            onPress={() => openFileManager(answer)}
            testID={`open-file-button-${index}`}
            buttonStyle={{ width: '100%', backgroundColor: '#1E90FF', marginTop: 8 }}
          />
        </View>
      );
    default:
      return <Text testID={`text-answer-${index}`}>{answer || answer === 0 ? answer : '-'}</Text>;
  }
};

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

  const handleRetake = async (questionKey) => {
    const allowed = await ensureCameraPermission();
    if (!allowed) {
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ base64: true });
    if (result?.canceled) {
      return;
    }
    setRetakingKey(questionKey);
    try {
      const { uri: imageUri } = result.assets[0];
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
      ToastAndroid.show(trans.retakeSuccess, ToastAndroid.LONG);
    } finally {
      setRetakingKey(null);
    }
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
          <ImageView
            key={`${q.id}-${answer}`}
            label={q.label}
            uri={answer}
            textTestID={`text-question-${qIndex}`}
            imageTestID={`image-question-${qIndex}`}
            missingText={trans.attachmentMissingText}
            retakeLabel={trans.buttonReattachFile}
            onRetake={canRetake ? () => handleReattach(q.id, q.rule) : null}
            isRetaking={retakingKey === q.id}
            processingLabel={trans.compressingImage}
          />
        );
      }
      return (
        <AttachmentView
          key={`${q.id}-${answer}`}
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
      return (
        <ImageView
          key={`${q.id}-${answer}`}
          label={q.label}
          uri={answer}
          textTestID={`text-question-${qIndex}`}
          imageTestID={`image-question-${qIndex}`}
          missingText={trans.fileMissingText}
          retakeLabel={trans.buttonRetakePhoto}
          onRetake={canRetake && q.type === QUESTION_TYPES.photo ? () => handleRetake(q.id) : null}
          isRetaking={retakingKey === q.id}
          processingLabel={trans.compressingImage}
        />
      );
    }
    return (
      <View key={q.keyform} style={styles.listItem}>
        <View style={styles.listItemContent}>
          <Text style={styles.listItemTitle} testID={`text-question-${qIndex}`}>
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
  title: {
    fontWeight: '700',
    fontSize: 14,
    marginBottom: 4,
  },
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
  containerImage: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: 16,
    backgroundColor: 'white',
    borderWidth: 1,
    borderTopColor: 'transparent',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: 'silver',
  },
  image: {
    width: '100%',
    height: 200,
    aspectRatio: 1,
  },
  missingText: {
    color: '#b91c1c',
    marginBottom: 8,
  },
  processingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 8,
  },
  processingText: {
    color: 'dodgerblue',
    fontSize: 14,
  },
  listItem: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  listItemContent: {
    flex: 1,
  },
  listItemTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 4,
  },
});

export default FormDataDetails;
