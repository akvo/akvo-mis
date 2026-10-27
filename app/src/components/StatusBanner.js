import React, { useCallback, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { UIState, DatapointSyncState } from '../store';
import { i18n } from '../lib';
import useTheme from '../lib/theme';
import { SYNC_STATUS } from '../lib/constants';

const TIMEOUT_DISMISS = 3000; // 3second
// Transient sync events and the theme.banner token that fills each.
const SYNC_EVENT_BG_KEY = {
  [SYNC_STATUS.on_progress]: 'syncBg',
  [SYNC_STATUS.re_sync]: 'syncBg',
  [SYNC_STATUS.success]: 'successBg',
};
// Plain per-status text, used when the caller's statusText is missing or has no entry.
const SYNC_FALLBACK_TEXT_KEY = {
  [SYNC_STATUS.on_progress]: 'syncingText',
  [SYNC_STATUS.re_sync]: 'reSyncingText',
  [SYNC_STATUS.success]: 'doneText',
  [SYNC_STATUS.failed]: 'syncErrorText',
  [SYNC_STATUS.rejected]: 'syncRejectedText',
};

/**
 * Pick the one banner to show, or null. Pure, so the precedence is testable on its own.
 *
 * Precedence: events interrupt, conditions resume.
 * 1. sync activity — transient, and it shows progress the user asked for
 * 2. low storage — a condition, and the only message here that predicts data loss
 * 3. sync failed / refused — sticky, so neither must mask (2). Low storage still
 *    outranks a refusal: the refused answers are safe as a draft, storage loss is not.
 * 4. offline — normal in the field, so it sits below (2) as well
 */
export const resolveBanner = ({
  syncType: rawSyncType,
  isOnline,
  lowStorage,
  statusText,
  theme,
  trans,
}) => {
  // A sync status left over from before the connection dropped is stale: offline must not be
  // masked by it. Nulled here, not in the caller, so every caller gets it. Not an early
  // `!isOnline` return, because low storage still outranks offline.
  const syncType = isOnline ? rawSyncType : null;
  const syncText = statusText?.[syncType] || trans[SYNC_FALLBACK_TEXT_KEY[syncType]];
  const eventBgKey = SYNC_EVENT_BG_KEY[syncType];
  if (eventBgKey) {
    return { bg: theme.banner[eventBgKey], color: theme.banner.onSync, text: syncText };
  }
  if (lowStorage) {
    return {
      bg: theme.status.warning,
      color: theme.banner.onWarning,
      text: trans.lowStorageText,
      isLowStorage: true,
    };
  }
  if (syncType === SYNC_STATUS.failed || syncType === SYNC_STATUS.rejected) {
    return { bg: theme.status.error, color: theme.banner.onError, text: syncText };
  }
  if (!isOnline) {
    return { bg: theme.text.tertiary, color: theme.banner.onMuted, text: trans.offlineText };
  }
  return null;
};

const StatusBanner = () => {
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

  const banner = resolveBanner({
    syncType: statusBar?.type,
    isOnline,
    lowStorage,
    statusText,
    theme,
    trans,
  });

  const bannerVisible = !!banner;
  useEffect(() => {
    UIState.update((s) => {
      s.bannerVisible = bannerVisible;
    });
  }, [bannerVisible]);

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
