import React, { useState, useMemo } from 'react';
import { View, StyleSheet, Text, TouchableOpacity } from 'react-native';
import { Switch } from '@rneui/themed';
import * as Crypto from 'expo-crypto';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout } from '../../components';
import { config } from './config';
import { BuildParamsState, UIState, AuthState, UserState } from '../../store';
import DialogForm from './DialogForm';
import { i18n } from '../../lib';
import { accuracyLevels } from '../../lib/loc';
import { crudConfig } from '../../database/crud';

// Define quality options inline to avoid importing expo-image-manipulator at module load time
const imageQualityOptions = [
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
  { label: 'Original', value: 'original' },
];

const SettingsForm = ({ route }) => {
  const [edit, setEdit] = useState(null);
  const [showDialog, setShowDialog] = useState(false);

  const {
    serverURL,
    dataSyncInterval,
    gpsThreshold,
    gpsAccuracyLevel,
    geoLocationTimeout,
    imageQuality,
  } = BuildParamsState.useState((s) => s);
  const { password, authenticationCode, useAuthenticationCode } = AuthState.useState((s) => s);
  const { lang, isDarkMode, fontSize } = UIState.useState((s) => s);
  const { name, syncWifiOnly } = UserState.useState((s) => s);
  const store = useMemo(
    () => ({
      AuthState,
      BuildParamsState,
      UIState,
      UserState,
    }),
    [],
  );
  const [settingsState, setSettingsState] = useState({
    serverURL,
    name,
    password,
    authenticationCode,
    useAuthenticationCode,
    lang,
    isDarkMode,
    fontSize,
    dataSyncInterval,
    syncWifiOnly,
    gpsThreshold,
    gpsAccuracyLevel,
    geoLocationTimeout,
    imageQuality,
  });

  const nonEnglish = lang !== 'en';
  const curConfig = config.find((c) => c.id === route?.params?.id);
  const pageTitle = nonEnglish ? i18n.transform(lang, curConfig)?.name : route?.params?.name;
  const db = useSQLiteContext();

  const editState = useMemo(() => {
    if (edit && edit?.key) {
      const [stateName, stateKey] = edit?.key?.split('.') || [];
      return [store[stateName], stateKey];
    }
    return null;
  }, [edit, store]);

  const handleEditPress = (id) => {
    const findEdit = list.find((item) => item.id === id);
    if (findEdit) {
      setEdit({
        ...findEdit,
        value: settingsState[findEdit?.name] || null,
      });
      setShowDialog(true);
    }
  };

  const handleUpdateOnDB = async (field, value) => {
    const configFields = [
      'apVersion',
      'authenticationCode',
      'serverURL',
      'syncInterval',
      'syncWifiOnly',
      'lang',
      'gpsThreshold',
      'gpsAccuracyLevel',
      'geoLocationTimeout',
      'imageQuality',
    ];
    if (configFields.includes(field)) {
      await crudConfig.updateConfig(db, { [field]: value });
    }
    if (field === 'name') {
      await crudConfig.updateConfig(db, { name: value });
    }
    if (field === 'password') {
      const encrypted = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA1, value);
      await crudConfig.updateConfig(db, { password: encrypted });
    }
  };

  const handleOKPress = async (inputValue) => {
    setShowDialog(false);
    if (edit && inputValue) {
      const [stateData, stateKey] = editState;
      stateData.update((d) => {
        d[stateKey] = inputValue;
      });
      setSettingsState({
        ...settingsState,
        [stateKey]: inputValue,
      });
      if (stateKey === 'dataSyncInterval') {
        await handleUpdateOnDB('syncInterval', inputValue);
      } else {
        await handleUpdateOnDB(stateKey, inputValue);
      }
      setEdit(null);
    }
  };
  const handleCancelPress = () => {
    setShowDialog(false);
    setEdit(null);
  };

  const handleOnSwitch = async (value, key) => {
    const [stateName, stateKey] = key.split('.');
    const tinyIntVal = value ? 1 : 0;
    store[stateName].update((s) => {
      s[stateKey] = tinyIntVal;
    });
    setSettingsState({
      ...settingsState,
      [stateKey]: tinyIntVal,
    });
    try {
      await handleUpdateOnDB(stateKey, tinyIntVal);
    } catch (err) {
      Sentry.captureException(err);
    }
  };

  const renderSubtitle = ({ type: inputType, name: fieldName, description }) => {
    const itemDesc = nonEnglish ? i18n.transform(lang, description)?.name : description?.name;
    if (inputType === 'switch' || inputType === 'password') {
      return itemDesc;
    }
    if (fieldName === 'gpsAccuracyLevel' && settingsState?.[fieldName]) {
      const findLevel = accuracyLevels.find((l) => l.value === settingsState[fieldName]);
      return findLevel?.label || itemDesc;
    }
    if (fieldName === 'imageQuality' && settingsState?.[fieldName]) {
      const findQuality = imageQualityOptions.find((q) => q.value === settingsState[fieldName]);
      return findQuality?.label || itemDesc;
    }
    return settingsState?.[fieldName];
  };

  const list = useMemo(() => {
    if (route.params?.id) {
      const findConfig = config.find((c) => c?.id === route.params.id);
      return findConfig ? findConfig.fields : [];
    }
    return [];
  }, [route.params?.id]);

  return (
    <BaseLayout title={pageTitle} rightComponent={false}>
      <BaseLayout.Content>
        <View>
          {list.map((l, i) => {
            const itemTitle = nonEnglish ? i18n.transform(lang, l)?.label : l.label;
            return (
              <TouchableOpacity
                key={l.id}
                testID={`settings-form-item-${i}`}
                onPress={() => {
                  if (l.editable && l.type !== 'switch') {
                    handleEditPress(l.id);
                  }
                }}
                style={styles.listItem}
              >
                <View style={styles.itemContent}>
                  <Text style={styles.itemTitle}>{itemTitle}</Text>
                  <Text style={styles.itemSubtitle}>{renderSubtitle(l)}</Text>
                </View>
                {l.type === 'switch' && (
                  <Switch
                    onValueChange={(value) => handleOnSwitch(value, l.key)}
                    value={settingsState?.[l.name] === 1}
                    testID={`settings-form-switch-${i}`}
                  />
                )}
              </TouchableOpacity>
            );
          })}
        </View>
        <DialogForm
          onOk={handleOKPress}
          onCancel={handleCancelPress}
          showDialog={showDialog}
          edit={edit}
          initValue={edit?.value}
        />
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 15,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  itemContent: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: '500',
  },
  itemSubtitle: {
    fontSize: 14,
    color: '#666',
  },
});

export default SettingsForm;
