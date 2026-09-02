import React, { useEffect, useState } from 'react';
import { View, Text, Alert, ActivityIndicator, Platform, ToastAndroid } from 'react-native';
import { Button } from '@rneui/themed';
import * as Linking from 'expo-linking';
import * as FileSystem from 'expo-file-system';
import * as IntentLauncher from 'expo-intent-launcher';
import * as Sentry from '@sentry/react-native';
import MIME_TYPES from '../../lib/mime_types';
import styles from './styles';

const AttachmentView = ({
  label,
  uri,
  index,
  onReattach = null,
  missingText = '',
  reattachLabel = '',
  openLabel = '',
  openFailedText = '',
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
    try {
      // Server-hosted file: the browser downloads or displays it.
      if (!uri.startsWith('file://') || Platform.OS !== 'android') {
        await Linking.openURL(uri);
        return;
      }
      // A raw file:// uri cannot cross an app boundary on Android (API 24+) — it
      // raises FileUriExposedException. getContentUriAsync wraps it in a
      // FileProvider content:// uri, and the read-permission flag lets the
      // receiving app actually open it.
      const contentUri = await FileSystem.getContentUriAsync(uri);
      const extension = uri.split('/').pop().split('.').pop().toLowerCase();
      await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
        data: contentUri,
        flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
        // Without an explicit type Android often resolves no activity at all,
        // even when a capable app is installed.
        type: MIME_TYPES[extension] || 'application/octet-stream',
      });
    } catch (error) {
      // Thrown when no installed app can handle the type — a dead end for the user
      // either way, so say so instead of failing silently.
      Sentry.captureMessage(`[AttachmentView] no handler for attachment: ${uri}`);
      Sentry.captureException(error);
      if (Platform.OS === 'android') {
        ToastAndroid.show(openFailedText, ToastAndroid.LONG);
      } else {
        Alert.alert(openFailedText);
      }
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
