import { useState, useEffect, useCallback, useRef } from 'react';
import { Linking, Alert } from 'react-native';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';
import { BuildParamsState, UIState } from '../store';
import { api, i18n } from '../lib';
import { SKIP_UPDATE_DURATION_MS } from '../lib/constants';
import crudConfig from '../database/crud/crud-config';

const useVersionCheck = ({ autoCheck = false } = {}) => {
  const { appVersion, apkURL } = BuildParamsState.useState((s) => s);
  const isOnline = UIState.useState((s) => s.online);
  const { lang } = UIState.useState((s) => s);
  const trans = i18n.text(lang);
  const db = useSQLiteContext();

  const [visible, setVisible] = useState(false);
  const [checking, setChecking] = useState(false);
  const [updateInfo, setUpdateInfo] = useState({ status: null, text: '' });
  const hasChecked = useRef(false);

  const checkVersion = useCallback(
    async (silent = false) => {
      if (!isOnline) {
        return;
      }
      if (silent) {
        // Suppress the unsolicited prompt while the user's "Later" window is open.
        // Checked before the request so a dismissed user spends no bandwidth.
        const config = await crudConfig.getConfig(db);
        const skippedUntil = config?.updateSkippedUntil;
        if (skippedUntil && new Date(skippedUntil) > new Date()) {
          return;
        }
      }
      setChecking(true);
      if (!silent) {
        setVisible(true);
      }
      api
        .get(`/apk/version/${appVersion}`)
        .then((res) => {
          setUpdateInfo({
            status: 200,
            text: `${trans.newVersionAvailable} (v ${res.data.version})`,
          });
          if (silent) {
            setVisible(true);
          }
        })
        .catch((e) => {
          setUpdateInfo({ status: e?.response?.status || 500, text: trans.noUpdateFound });
          if (e?.response?.status !== 404) {
            Sentry.captureMessage('[VersionCheck] Unable to fetch app version');
            Sentry.captureException(e);
          }
        })
        .finally(() => {
          setChecking(false);
        });
    },
    [db, appVersion, isOnline, trans.newVersionAvailable, trans.noUpdateFound],
  );

  const handleUpdate = useCallback(async () => {
    if (!apkURL) {
      Sentry.captureMessage('[VersionCheck] apkURL is missing — cannot open update');
      Alert.alert('Update URL is not configured. Please contact support.');
      return;
    }
    const supported = await Linking.canOpenURL(apkURL);
    if (supported) {
      await Linking.openURL(apkURL);
    } else {
      Alert.alert(`Don't know how to open this URL: ${apkURL}`);
    }
  }, [apkURL]);

  const handleSkip = useCallback(async () => {
    // Close first: a failed write must never re-trap the user in the dialog.
    setVisible(false);
    try {
      const skipUntil = new Date(Date.now() + SKIP_UPDATE_DURATION_MS).toISOString();
      await crudConfig.updateConfig(db, { updateSkippedUntil: skipUntil });
    } catch (error) {
      Sentry.captureMessage('[VersionCheck] Unable to persist update skip');
      Sentry.captureException(error);
    }
  }, [db]);

  useEffect(() => {
    if (!autoCheck || hasChecked.current) {
      return;
    }
    // One-shot per mount: lock the gate even when offline so a late
    // online-flip cannot trigger a delayed force-update dialog mid-session.
    hasChecked.current = true;
    if (isOnline) {
      checkVersion(true);
    }
  }, [autoCheck, isOnline, checkVersion]);

  return { visible, setVisible, checking, updateInfo, checkVersion, handleUpdate, handleSkip };
};

export default useVersionCheck;
