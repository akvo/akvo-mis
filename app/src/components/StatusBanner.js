import React, { useCallback, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { UIState, DatapointSyncState } from '../store';
import { i18n } from '../lib';
import { SYNC_STATUS } from '../lib/constants';

const TIMEOUT_DISMISS = 3000; // 3second

const StatusBanner = () => {
  const insets = useSafeAreaInsets();
  const isOnline = UIState.useState((s) => s.online);
  const activeLang = UIState.useState((s) => s.lang);
  const statusBar = UIState.useState((s) => s.statusBar);
  const lowStorage = UIState.useState((s) => s.lowStorage);
  const syncProgress = DatapointSyncState.useState((s) => s.progress);
  const syncInProgress = DatapointSyncState.useState((s) => s.inProgress);
  const trans = i18n.text(activeLang);
  const statusBg = isOnline ? statusBar?.bgColor || '#ef4444' : '#ef4444';
  const statusIc = isOnline ? statusBar?.icon || 'cloud-offline' : 'cloud-offline';

  const getSyncPhaseLabel = () => {
    const { syncPhase } = statusBar || {};
    if (syncPhase === 'uploading') return trans.uploadingSubmissionsText;
    if (syncPhase === 'syncing_drafts') return trans.syncingDraftsText;
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
   * 3. sync failed — sticky and unactionable from this bar, so it must not mask (2)
   * 4. offline — normal in the field, so it sits below (2) as well
   */
  const syncType = isOnline ? statusBar?.type : null;
  const isSyncEvent = [SYNC_STATUS.on_progress, SYNC_STATUS.re_sync, SYNC_STATUS.success].includes(
    syncType,
  );

  let banner = null;
  if (isSyncEvent) {
    banner = { bg: statusBg, icon: statusIc, text: statusText?.[syncType] || trans.offlineText };
  } else if (lowStorage) {
    // Amber, not the red used for offline and errors: a warning to act on, not a
    // failure that already happened.
    // One message for every context. "Sync now" only reclaims space by deleting
    // photos already uploaded, so it is impossible advice on a signed-out device and
    // useless to a signed-in one with nothing pending. Freeing device storage always
    // works.
    banner = { bg: '#f59e0b', icon: 'warning', text: trans.lowStorageText, isLowStorage: true };
  } else if (syncType === SYNC_STATUS.failed) {
    banner = { bg: statusBg, icon: statusIc, text: statusText?.[syncType] };
  } else if (!isOnline) {
    banner = { bg: '#ef4444', icon: 'cloud-offline', text: trans.offlineText };
  }

  if (!banner) {
    return null;
  }

  return (
    <View
      testID={banner.isLowStorage ? 'status-bar-low-storage' : 'status-bar'}
      style={{
        ...styles.container,
        backgroundColor: banner.bg,
        marginBottom: insets.bottom,
      }}
    >
      <Icon name={banner.icon} testID="offline-icon" style={styles.icon} />
      <Text style={styles.text} testID="offline-text">
        {banner.text}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 4,
    paddingVertical: 10,
    display: 'flex',
    gap: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { fontSize: 14, color: '#f5f5f5' },
  icon: {
    fontSize: 14,
    color: '#f5f5f5',
  },
});

export default StatusBanner;
