import React, { useMemo, useState } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { Button, Text, Image } from '@rneui/themed';
import * as DocumentPicker from 'expo-document-picker';
import Icon from 'react-native-vector-icons/Ionicons';
import * as Linking from 'expo-linking';
import { FieldLabel } from '../support';
import { FormState } from '../../store';
import { helpers, i18n } from '../../lib';
import { persistImage } from '../../lib/image-compressor';
import MIME_TYPES from '../../lib/mime_types';

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
        // Move out of the purgeable cache dir so the file survives until synced
        onChange(id, await persistImage(result?.uri, 'attachments'));
        setSelectedFile(result);
      }
    } catch (error) {
      // Handle any errors that occur during document picking
      // by showing an alert instead of console.log
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
          <Image source={{ uri: value }} style={styles.image} />
          <Button
            icon={<Icon name="trash" size={20} color="white" style={styles.Icon} />}
            title={trans.buttonRemove}
            onPress={onRemovePress}
            testID="remove-file-button"
            accessibilityLabel="remove-file-button"
            buttonStyle={styles.removeButton}
          />
        </View>
      )}
      {selectedFile?.name && !helpers.isImageFile(fileType) && (
        <View style={{ marginBottom: 10 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Icon name="document-text" size={20} color="black" style={styles.Icon} />
            <Text style={styles.fileName}>{fileName}</Text>
          </View>
          <Button
            icon={<Icon name="eye" size={20} color="white" style={styles.Icon} />}
            title={trans.openFileButton}
            onPress={() => onOpenPress(selectedFile?.uri)}
            testID="open-file-button"
            accessibilityLabel="open-file-button"
            buttonStyle={styles.attachButton}
          />
          <Button
            icon={<Icon name="trash" size={20} color="white" style={styles.Icon} />}
            title={trans.buttonRemove}
            onPress={onRemovePress}
            testID="remove-file-button"
            accessibilityLabel="remove-file-button"
            buttonStyle={styles.removeButton}
          />
        </View>
      )}
      {!value && (
        <Button
          icon={<Icon name="attach" size={20} color="white" style={styles.Icon} />}
          title={trans.attachButton}
          onPress={onPickerPress}
          testID="attach-file-button"
          accessibilityLabel="attach-file-button"
          buttonStyle={styles.attachButton}
        />
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
  removeButton: {
    backgroundColor: '#ec003f',
    marginTop: 10,
  },
  attachButton: {
    backgroundColor: '#1E90FF',
    marginTop: 10,
  },
  fileName: {
    marginBottom: 10,
  },
  Icon: {
    marginRight: 10,
  },
  image: {
    width: '100%',
    height: 200,
    aspectRatio: 1,
  },
});
