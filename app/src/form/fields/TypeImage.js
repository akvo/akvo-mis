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
  const activeLang = FormState.useState((s) => s.lang);
  const imageQuality = BuildParamsState.useState((s) => s.imageQuality);
  const saveToGallery = BuildParamsState.useState((s) => s.saveToGallery);
  // Album name follows the build's app name rather than a literal, so a
  // rebranded APK groups its photos under its own name
  const apkName = BuildParamsState.useState((s) => s.apkName);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;

  const [isCompressing, setIsCompressing] = useState(false);
  const [fileSize, setFileSize] = useState(null);
  // Remember which uri failed rather than a boolean: picking a new photo changes
  // `value`, so the comparison below goes false on its own — no reset needed.
  const [failedUri, setFailedUri] = useState(null);

  /**
   * Best-effort mirror of a capture into the device gallery, so a photo the app
   * later loses (cache purge, data clear, restore) can still be recovered by the
   * enumerator through the "From Gallery" repair flow.
   *
   * Never throws into the caller: an answer attached to a form is worth more than
   * its gallery copy, so a denied permission or a failed write is reported and
   * swallowed.
   */
  const copyToGallery = async (uri) => {
    try {
      // Full access, not write-only: grouping into an album needs to *read*
      // MediaStore to find whether the album already exists. With write-only the
      // asset lands in the default camera bucket and getAlbumAsync fails.
      const { granted } = await MediaLibrary.requestPermissionsAsync();
      if (!granted) {
        return;
      }
      const asset = await MediaLibrary.createAssetAsync(uri);
      const album = await MediaLibrary.getAlbumAsync(apkName);
      // `false` means move rather than copy — copying would leave a duplicate in
      // the camera bucket and double the storage this feature costs.
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
    /**
     * Property fileName is only available for iOS
     * docs: https://docs.expo.dev/versions/latest/sdk/imagepicker/#imagepickerasset
     */
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
      // Set the answer first so the preview appears without waiting on the
      // gallery write. A photo picked from the library is already there, so
      // only camera captures are mirrored.
      onChange(id, persisted);
      if (fromCamera && saveToGallery) {
        await copyToGallery(persisted);
      }
    } finally {
      setIsCompressing(false);
    }
  };

  const selectFile = async () => {
    /**
     * No permissions request is necessary for launching the image library
     * Docs: https://docs.expo.dev/versions/latest/sdk/imagepicker/#usage
     */
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

  return (
    <View style={{ marginBottom: 20 }}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View style={styles.fieldImageContainer}>
        <Button
          type="outline"
          onPress={handleCamera}
          testID="btn-use-camera"
          disabled={isCompressing}
        >
          <Icon name="camera" size={18} color="dodgerblue" />
          {` ${trans.buttonUseCamera}`}
        </Button>
        {useGallery && (
          <Button
            type="outline"
            onPress={selectFile}
            testID="btn-from-gallery"
            disabled={isCompressing}
          >
            <Icon name="image" size={18} color="dodgerblue" />
            {` ${trans.buttonFromGallery}`}
          </Button>
        )}
        {isCompressing && (
          <View style={styles.compressingContainer}>
            <ActivityIndicator size="small" color="dodgerblue" />
            <Text style={styles.compressingText}>{trans.compressingImage || 'Compressing...'}</Text>
          </View>
        )}
        {value && typeof value === 'string' && !isCompressing && (
          <View>
            {failedUri === value ? (
              <Text style={styles.missingText} testID="image-missing">
                {trans.photoMissingText}
              </Text>
            ) : (
              <Image
                source={{ uri: value }}
                style={styles.imagePreview}
                PlaceholderContent={<ActivityIndicator />}
                testID="image-preview"
                onError={() => setFailedUri(value)}
              />
            )}
            {fileSize !== null && (
              <Text style={styles.fileSizeText}>{formatFileSize(fileSize)}</Text>
            )}
            <Button
              containerStyle={styles.buttonRemoveFile}
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

const styles = StyleSheet.create({
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
    color: 'dodgerblue',
    fontSize: 14,
  },
  fileSizeText: {
    textAlign: 'center',
    color: '#666',
    fontSize: 12,
    marginTop: 4,
  },
  missingText: {
    color: '#b91c1c',
    textAlign: 'center',
    paddingVertical: 12,
  },
});
