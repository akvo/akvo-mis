import React, { useCallback, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { UIState, DatapointSyncState, AuthState } from '../store';
import { i18n } from '../lib';
import useTheme from '../lib/theme';
import { SYNC_STATUS } from '../lib/constants';

const TIMEOUT_DISMISS = 3000; // 3second
const TAB_BAR_BASE = 70;

const StatusBanner = () => {
  const insets = useSafeAreaInsets();
  const token = AuthState.useState((s) => s.token);
  const isOnline = UIState.useState((s) => s.online);
  const activeLang = UIState.useState((s) => s.lang);
  const statusBar = UIState.useState((s) => s.statusBar);
  const lowStorage = UIState.useState((s) => s.lowStorage);
  const syncProgress = DatapointSyncState.useState((s) => s.progress);
  const syncInProgress = DatapointSyncState.useState((s) => s.inProgress);
  const theme = useTheme();
  const trans = i18n.text(activeLang);

  const getSyncPhaseLabel = () => {
    const { syncPhase } = statusBar || {};
    if (syncPhase === 'uploading') {
      return trans.uploadingSubmissionsText;
    }
    if (syncPhase === 'syncing_drafts') {
      return trans.syncingDraftsText;
    }
    if (syncPhase === 'downloading') {
      return syncInProgress && syncProgress > 0
        ? `${trans.downloadingDatapointsText} ${Math.round(syncProgress)}%`
        : trans.downloadingDatapointsText;
    }
    return syncInProgress && syncProgress > 0
      ? `${trans.syncingText} ${Math.round(syncProgress)}%`
      : trans.syncingText;
  };

  const statusText = {
    1: getSyncPhaseLabel(),
    2: trans.reSyncingText,
    3: trans.doneText,
    4: trans.syncErrorText,
    5: trans.syncRejectedText,
  };

  const handleOnResetStatusBar = useCallback(() => {
    /**
     * Check only for final result
     */
    if (statusBar?.type === SYNC_STATUS.success) {
      setTimeout(() => {
        UIState.update((s) => {
          s.statusBar = null;
        });
      }, TIMEOUT_DISMISS);
    }
  }, [statusBar]);

  useEffect(() => {
    handleOnResetStatusBar();
  }, [handleOnResetStatusBar]);

  /**
   * Precedence: events interrupt, conditions resume.
   * 1. sync activity — transient, and it shows progress the user asked for
   * 2. low storage — a condition, and the only message here that predicts data loss
   * 3. sync failed / refused — sticky, so neither must mask (2). Low storage still
   *    outranks a refusal: the refused answers are safe as a draft, storage loss is not.
   * 4. offline — normal in the field, so it sits below (2) as well
   */
  const syncType = isOnline ? statusBar?.type : null;
  const isSyncEvent = [SYNC_STATUS.on_progress, SYNC_STATUS.re_sync, SYNC_STATUS.success].includes(
    syncType,
  );

  const getBannerColor = () => {
    if (syncType === SYNC_STATUS.success) {
      return '#5BFF53';
    }
    if (syncType === SYNC_STATUS.on_progress || syncType === SYNC_STATUS.re_sync) {
      return '#83DCFF';
    }
    return theme.status.error;
  };

  const DARK_TEXT = '#000000';
  const LIGHT_TEXT = '#FFFFFF';

  let banner = null;
  if (isSyncEvent) {
    const bg = getBannerColor();
    const useDark = syncType === SYNC_STATUS.success || syncType === SYNC_STATUS.on_progress || syncType === SYNC_STATUS.re_sync;
    banner = {
      bg,
      color: useDark ? DARK_TEXT : LIGHT_TEXT,
      text: statusText?.[syncType] || trans.offlineText,
    };
  } else if (lowStorage) {
    banner = {
      bg: theme.status.warning,
      color: DARK_TEXT,
      text: trans.lowStorageText,
      isLowStorage: true,
    };
  } else if (syncType === SYNC_STATUS.failed || syncType === SYNC_STATUS.rejected) {
    banner = {
      bg: theme.status.error,
      color: LIGHT_TEXT,
      text: statusText?.[syncType],
    };
  } else if (!isOnline) {
    banner = { bg: theme.text.tertiary, color: LIGHT_TEXT, text: trans.offlineText };
  }

  if (!banner) {
    return null;
  }

  return (
    <View
      testID={banner.isLowStorage ? 'status-bar-low-storage' : 'status-bar'}
      style={[
        styles.container,
        {
          backgroundColor: banner.bg,
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: token ? TAB_BAR_BASE + Math.max(insets.bottom, 10) : insets.bottom,
          zIndex: 10,
        },
      ]}
    >
      <View testID="offline-icon" style={[styles.dot, { backgroundColor: banner.color }]} />
      <Text style={[styles.text, { color: banner.color }]} testID="offline-text">
        {banner.text}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    display: 'flex',
    gap: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 0,
  },
  text: { fontSize: 14, fontWeight: '500' },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
});

export default StatusBanner;
