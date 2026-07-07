import React, { useState } from 'react';
import { View, PermissionsAndroid, StyleSheet, ActivityIndicator, Text } from 'react-native';
import { Image, Button } from '@rneui/themed';
import * as ImagePicker from 'expo-image-picker';
import Icon from 'react-native-vector-icons/Ionicons';

import { FieldLabel } from '../support';
import { FormState, BuildParamsState } from '../../store';
import { i18n } from '../../lib';
import { compressImage, formatFileSize } from '../../lib/image-compressor';

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
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;

  const [isCompressing, setIsCompressing] = useState(false);
  const [fileSize, setFileSize] = useState(null);

  const handleOnChange = async (dataResult) => {
    const { uri: imageUri } = dataResult.assets[0];
    /**
     * Property fileName is only available for iOS
     * docs: https://docs.expo.dev/versions/latest/sdk/imagepicker/#imagepickerasset
     */
    setIsCompressing(true);
    try {
      const result = await compressImage(imageUri, imageQuality);
      setFileSize(result.size);
      onChange(id, result.uri);
    } catch (error) {
      console.error('[TypeImage] Compression error:', error);
      setFileSize(null);
      onChange(id, imageUri);
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
        await handleOnChange(result);
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
            <Image
              source={{ uri: value }}
              style={styles.imagePreview}
              PlaceholderContent={<ActivityIndicator />}
              testID="image-preview"
            />
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
});
