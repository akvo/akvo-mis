import React, { useEffect, useState } from 'react';
import { View, Text, Alert, ActivityIndicator } from 'react-native';
import { Button } from '@rneui/themed';
import * as Linking from 'expo-linking';
import * as FileSystem from 'expo-file-system';
import styles from './styles';

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

export default AttachmentView;
