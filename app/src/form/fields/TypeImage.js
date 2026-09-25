import React, { useState } from 'react';
import { View, PermissionsAndroid, StyleSheet, ActivityIndicator, Text } from 'react-native';
import { Image, Button } from '@rneui/themed';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import * as Sentry from '@sentry/react-native';
import Icon from 'react-native-vector-icons/Ionicons';

import { FieldLabel } from '../support';
import { FormState, BuildParamsState } from '../../store';
import { i18n } from '../../lib';
import { compressImage, formatFileSize, persistImage } from '../../lib/image-compressor';
import useTheme from '../../lib/theme';

const TypeImage = ({
  onChange,
  keyform,
  id,
  value,
  label,
  required,
  requiredSign = '*',
  useGallery = false,
  tooltip = null,
}) => {
  const theme = useTheme();
  const activeLang = FormState.useState((s) => s.lang);
  const imageQuality = BuildParamsState.useState((s) => s.imageQuality);
  const saveToGallery = BuildParamsState.useState((s) => s.saveToGallery);
  const apkName = BuildParamsState.useState((s) => s.apkName);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;

  const [isCompressing, setIsCompressing] = useState(false);
  const [fileSize, setFileSize] = useState(null);
  const [failedUri, setFailedUri] = useState(null);

  const copyToGallery = async (uri) => {
    try {
      const { granted } = await MediaLibrary.requestPermissionsAsync();
      if (!granted) {
        return;
      }
      const asset = await MediaLibrary.createAssetAsync(uri);
      const album = await MediaLibrary.getAlbumAsync(apkName);
      if (album) {
        await MediaLibrary.addAssetsToAlbumAsync([asset], album, false);
      } else {
        await MediaLibrary.createAlbumAsync(apkName, asset, false);
      }
    } catch (error) {
      Sentry.captureMessage(`[TypeImage] gallery copy failed for ${uri}`);
      Sentry.captureException(error);
    }
  };

  const handleOnChange = async (dataResult, fromCamera = false) => {
    const { uri: imageUri } = dataResult.assets[0];
    setIsCompressing(true);
    try {
      let persisted;
      try {
        const result = await compressImage(imageUri, imageQuality);
        setFileSize(result.size);
        persisted = await persistImage(result.uri);
      } catch (error) {
        console.error('[TypeImage] Compression error:', error);
        setFileSize(null);
        persisted = await persistImage(imageUri);
      }
      onChange(id, persisted);
      if (fromCamera && saveToGallery) {
        await copyToGallery(persisted);
      }
    } finally {
      setIsCompressing(false);
    }
  };

  const selectFile = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      base64: true,
    });
    if (!result?.canceled) {
      await handleOnChange(result);
    }
  };

  const handleCamera = async () => {
    const isCameraGranted = await PermissionsAndroid.check(PermissionsAndroid.PERMISSIONS.CAMERA);
    let accessGranted = isCameraGranted;
    if (!isCameraGranted) {
      const askCameraPermission = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.CAMERA,
        {
          title: trans.imageStoragePerm,
          message: trans.imageCameraPerm,
          buttonNeutral: trans.imageAskLater,
          buttonNegative: trans.buttonCancel,
          buttonPositive: trans.buttonOk,
        },
      );
      if (askCameraPermission !== PermissionsAndroid.RESULTS.GRANTED) {
        accessGranted = false;
      }
    }
    if (accessGranted) {
      const result = await ImagePicker.launchCameraAsync({
        base64: true,
      });
      if (!result?.canceled) {
        await handleOnChange(result, true);
      }
    }
  };

  const handleRemove = () => {
    setFileSize(null);
    onChange(id, null);
  };

  const themedStyles = getThemedStyles(theme);

  return (
    <View style={{ marginBottom: 20 }}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View style={themedStyles.fieldImageContainer}>
        <Button
          type="outline"
          onPress={handleCamera}
          testID="btn-use-camera"
          disabled={isCompressing}
        >
          <Icon name="camera" size={18} color={theme.icon.accent} />
          {` ${trans.buttonUseCamera}`}
        </Button>
        {useGallery && (
          <Button
            type="outline"
            onPress={selectFile}
            testID="btn-from-gallery"
            disabled={isCompressing}
          >
            <Icon name="image" size={18} color={theme.icon.accent} />
            {` ${trans.buttonFromGallery}`}
          </Button>
        )}
        {isCompressing && (
          <View style={themedStyles.compressingContainer}>
            <ActivityIndicator size="small" color={theme.icon.accent} />
            <Text style={[themedStyles.compressingText, { color: theme.icon.accent }]}>
              {trans.compressingImage || 'Compressing...'}
            </Text>
          </View>
        )}
        {value && typeof value === 'string' && !isCompressing && (
          <View>
            {failedUri === value ? (
              <Text style={[themedStyles.missingText, { color: theme.status.error }]} testID="image-missing">
                {trans.photoMissingText}
              </Text>
            ) : (
              <Image
                source={{ uri: value }}
                style={themedStyles.imagePreview}
                PlaceholderContent={<ActivityIndicator />}
                testID="image-preview"
                onError={() => setFailedUri(value)}
              />
            )}
            {fileSize !== null && (
              <Text style={[themedStyles.fileSizeText, { color: theme.text.tertiary }]}>
                {formatFileSize(fileSize)}
              </Text>
            )}
            <Button
              containerStyle={themedStyles.buttonRemoveFile}
              title={trans.buttonRemove}
              color="secondary"
              onPress={handleRemove}
              disabled={!value}
              testID="btn-remove"
            />
          </View>
        )}
      </View>
    </View>
  );
};

export default TypeImage;

const getThemedStyles = () =>
  StyleSheet.create({
    fieldImageContainer: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      gap: 8,
      paddingHorizontal: 16,
    },
    imagePreview: { width: '100%', height: 200, resizeMode: 'contain' },
    buttonRemoveFile: {
      paddingVertical: 8,
    },
    compressingContainer: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: 12,
      gap: 8,
    },
    compressingText: {
      fontSize: 14,
    },
    fileSizeText: {
      textAlign: 'center',
      fontSize: 12,
      marginTop: 4,
    },
    missingText: {
      textAlign: 'center',
      paddingVertical: 12,
    },
  });
