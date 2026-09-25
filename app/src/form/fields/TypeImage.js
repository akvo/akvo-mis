import React, { useState } from 'react';
import { View, PermissionsAndroid, StyleSheet, ActivityIndicator, Text, TouchableOpacity } from 'react-native';
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

  const s = getThemedStyles(theme);

  return (
    <View style={{ marginBottom: 14 }}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View style={s.card}>
        {/* Image preview or placeholder */}
        {value && typeof value === 'string' && !isCompressing ? (
          <View>
            {failedUri === value ? (
              <Text style={s.missingText} testID="image-missing">
                {trans.photoMissingText}
              </Text>
            ) : (
              <Image
                source={{ uri: value }}
                style={s.imagePreview}
                PlaceholderContent={<ActivityIndicator />}
                testID="image-preview"
                onError={() => setFailedUri(value)}
              />
            )}
            {fileSize !== null && (
              <Text style={[s.fileSizeText, { color: theme.text.tertiary }]}>
                {formatFileSize(fileSize)}
              </Text>
            )}
          </View>
        ) : (
          <View style={s.placeholder}>
            <Icon name="camera" size={32} color={theme.text.tertiary} />
          </View>
        )}

        {isCompressing && (
          <View style={s.compressingContainer}>
            <ActivityIndicator size="small" color={theme.buttonPrimary.bg} />
            <Text style={[s.compressingText, { color: theme.text.secondary }]}>
              {trans.compressingImage || 'Compressing...'}
            </Text>
          </View>
        )}

        {/* Action buttons */}
        {!value && !isCompressing && (
          <View style={s.buttonRow}>
            <Button
              onPress={handleCamera}
              testID="btn-use-camera"
              disabled={isCompressing}
              buttonStyle={s.cameraButton}
              titleStyle={s.cameraButtonText}
              icon={<Icon name="camera" size={18} color="#fff" style={{ marginRight: 6 }} />}
              title={trans.buttonUseCamera}
            />
            {useGallery && (
              <TouchableOpacity
                onPress={selectFile}
                testID="btn-from-gallery"
                disabled={isCompressing}
                style={s.galleryButton}
              >
                <Icon name="folder" size={18} color={theme.text.primary} style={{ marginRight: 6 }} />
                <Text style={[s.galleryButtonText, { color: theme.text.primary }]}>
                  {trans.buttonFromGallery}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Remove button when image exists */}
        {value && !isCompressing && (
          <TouchableOpacity
            onPress={handleRemove}
            testID="btn-remove"
            style={s.removeButton}
          >
            <Icon name="trash-outline" size={16} color={theme.status.error} style={{ marginRight: 6 }} />
            <Text style={{ color: theme.status.error, fontSize: 14, fontWeight: '600' }}>
              {trans.buttonRemove}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Info message */}
      {!value && (
        <View style={[s.infoContainer, { backgroundColor: theme.bg.surfaceElevated1 }]}>
          <Icon name="information-circle" size={22} color={theme.buttonPrimary.bg} style={{ marginRight: 8, marginTop: 2 }} />
          <Text style={[s.infoText, { color: theme.text.secondary }]}>
            {trans.photoSyncInfo || 'The photo stays on the phone until you sync. Once it reaches the server the local copy is deleted to free up storage.'}
          </Text>
        </View>
      )}
    </View>
  );
};

export default TypeImage;

const getThemedStyles = (theme) =>
  StyleSheet.create({
    card: {
      backgroundColor: theme.bg.surfaceElevated1,
      borderRadius: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border.listDivider,
      marginHorizontal: 10,
      padding: 16,
    },
    placeholder: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: 40,
    },
    imagePreview: {
      width: '100%',
      height: 200,
      resizeMode: 'contain',
      borderRadius: 8,
    },
    buttonRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 16,
    },
    cameraButton: {
      backgroundColor: theme.buttonPrimary.bg,
      borderRadius: 24,
      paddingVertical: 12,
      paddingHorizontal: 20,
    },
    cameraButtonText: {
      fontSize: 15,
      fontWeight: '600',
    },
    galleryButton: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 12,
      paddingHorizontal: 8,
    },
    galleryButtonText: {
      fontSize: 15,
      fontWeight: '600',
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
    removeButton: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: 12,
      paddingVertical: 10,
    },
    missingText: {
      textAlign: 'center',
      paddingVertical: 12,
      color: theme.status.error,
    },
    infoContainer: {
      flexDirection: 'row',
      marginHorizontal: 10,
      marginTop: 10,
      padding: 14,
      borderRadius: 12,
    },
    infoText: {
      fontSize: 14,
      lineHeight: 20,
      flex: 1,
    },
  });
