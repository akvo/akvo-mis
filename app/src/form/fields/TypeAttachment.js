import React, { useMemo, useState } from 'react';
import { View, StyleSheet, Alert, TouchableOpacity, Text } from 'react-native';
import { Image } from '@rneui/themed';
import * as DocumentPicker from 'expo-document-picker';
import Icon from 'react-native-vector-icons/Ionicons';
import * as Linking from 'expo-linking';
import { FieldLabel } from '../support';
import { FormState } from '../../store';
import { helpers, i18n } from '../../lib';
import { persistImage } from '../../lib/image-compressor';
import MIME_TYPES from '../../lib/mime_types';
import useTheme from '../../lib/theme';

const TypeAttachment = ({
  onChange,
  keyform,
  id,
  value,
  label,
  required,
  requiredSign = '*',
  tooltip = null,
  rule = null,
}) => {
  const theme = useTheme();
  const [selectedFile, setSelectedFile] = useState({ name: value });
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const { allowedFileTypes } = rule || {};
  const fileTypes = allowedFileTypes?.length
    ? allowedFileTypes.map((type) => MIME_TYPES?.[type] || 'application/octet-stream')
    : '*/*';

  const [fileName, fileType] = useMemo(() => {
    const fname = selectedFile?.name?.includes('/')
      ? selectedFile.name.split('/')?.pop()
      : selectedFile?.name;
    const ftype = fname?.split('.').pop();
    return [fname, ftype];
  }, [selectedFile]);

  const onPickerPress = async () => {
    try {
      const { assets, canceled } = await DocumentPicker.getDocumentAsync({
        multiple: false,
        type: fileTypes,
        copyToCacheDirectory: true,
      });
      if (!canceled && assets && assets.length > 0) {
        const result = assets[0];
        onChange(id, await persistImage(result?.uri, 'attachments'));
        setSelectedFile(result);
      }
    } catch (error) {
      Alert.alert('Error', 'An error occurred while picking the document. Please try again.');
    }
  };

  const onRemovePress = () => {
    setSelectedFile(null);
    onChange(id, null);
  };

  const onOpenPress = async (uri) => {
    const supported = await Linking.canOpenURL(uri);
    if (supported) {
      await Linking.openURL(uri);
    } else {
      Alert.alert("Don't know how to open this URL:", uri);
    }
  };

  return (
    <View style={styles.container}>
      <FieldLabel
        keyform={keyform}
        name={label}
        required={required}
        requiredSign={requiredSign}
        tooltip={tooltip}
      />
      {value && helpers.isImageFile(fileType) && (
        <View style={{ marginBottom: 10 }}>
          <Image source={{ uri: value }} style={[styles.image, { borderRadius: 12 }]} />
          <TouchableOpacity
            style={[styles.pillButton, { backgroundColor: theme.status.error, marginTop: 10 }]}
            onPress={onRemovePress}
            testID="remove-file-button"
            accessibilityLabel="remove-file-button"
          >
            <Icon name="trash" size={18} color="#FFFFFF" />
            <Text style={styles.pillButtonText}>{trans.buttonRemove}</Text>
          </TouchableOpacity>
        </View>
      )}
      {selectedFile?.name && !helpers.isImageFile(fileType) && (
        <View style={{ marginBottom: 10 }}>
          <View style={[styles.fileRow, { backgroundColor: theme.bg.surfaceTertiary }]}>
            <Icon name="document-text" size={20} color={theme.icon.primary} />
            <Text style={[styles.fileName, { color: theme.text.primary }]}>{fileName}</Text>
          </View>
          <TouchableOpacity
            style={[styles.pillButton, { backgroundColor: theme.buttonPrimary.bg, marginTop: 10 }]}
            onPress={() => onOpenPress(selectedFile?.uri)}
            testID="open-file-button"
            accessibilityLabel="open-file-button"
          >
            <Icon name="eye" size={18} color={theme.buttonPrimary.text} />
            <Text style={[styles.pillButtonText, { color: theme.buttonPrimary.text }]}>
              {trans.openFileButton}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.pillButton, { backgroundColor: theme.status.error, marginTop: 10 }]}
            onPress={onRemovePress}
            testID="remove-file-button"
            accessibilityLabel="remove-file-button"
          >
            <Icon name="trash" size={18} color="#FFFFFF" />
            <Text style={styles.pillButtonText}>{trans.buttonRemove}</Text>
          </TouchableOpacity>
        </View>
      )}
      {!value && (
        <TouchableOpacity
          style={[styles.pillButton, { backgroundColor: theme.buttonPrimary.bg, marginTop: 10 }]}
          onPress={onPickerPress}
          testID="attach-file-button"
          accessibilityLabel="attach-file-button"
        >
          <Icon name="attach" size={18} color={theme.buttonPrimary.text} />
          <Text style={[styles.pillButtonText, { color: theme.buttonPrimary.text }]}>
            {trans.attachButton}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

export default TypeAttachment;

const styles = StyleSheet.create({
  container: {
    flexDirection: 'column',
    marginBottom: 10,
  },
  fileName: {
    flex: 1,
  },
  fileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 14,
    borderRadius: 12,
  },
  image: {
    width: '100%',
    height: 200,
    aspectRatio: 1,
  },
  pillButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 24,
    marginHorizontal: 10,
    gap: 8,
  },
  pillButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
