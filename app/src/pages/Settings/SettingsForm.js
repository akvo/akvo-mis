import React, { useState, useMemo } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import * as Crypto from 'expo-crypto';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout, MessageNote, SettingRow, SettingSection } from '../../components';
import { config } from './config';
import { BuildParamsState, UIState, AuthState, UserState } from '../../store';
import DialogForm from './DialogForm';
import { i18n } from '../../lib';
import { crudConfig } from '../../database/crud';

const getControl = (field) => {
  if (field.type === 'switch') {
    return 'toggle';
  }
  return field.levelKind ? 'level' : 'value';
};

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
    saveToGallery,
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
    saveToGallery,
  });

  const nonEnglish = lang !== 'en';
  const trans = i18n.text(lang);
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
      'saveToGallery',
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

  const describe = (description) =>
    nonEnglish ? i18n.transform(lang, description)?.name : description?.name;

  const renderValue = ({ type: fieldType, name: fieldName, unit, options }) => {
    const current = settingsState?.[fieldName];
    if (fieldType === 'switch') {
      return current === 1;
    }
    if (options) {
      return options.find((o) => o.value === current)?.label || '';
    }
    if (current === null || current === undefined || current === '') {
      return '';
    }
    return unit ? `${current} ${unit}` : `${current}`;
  };

  const list = useMemo(() => {
    if (route.params?.id) {
      const findConfig = config.find((c) => c?.id === route.params.id);
      return findConfig ? findConfig.fields : [];
    }
    return [];
  }, [route.params?.id]);

  // Consecutive fields sharing a `group` render under one section title; `index` keeps the
  // row testIDs numbered across the whole page.
  const sections = useMemo(
    () =>
      list.reduce((acc, field, index) => {
        const last = acc[acc.length - 1];
        if (last && last.group === field.group) {
          last.fields.push({ field, index });
          return acc;
        }
        return [...acc, { group: field.group, fields: [{ field, index }] }];
      }, []),
    [list],
  );

  return (
    <BaseLayout title={pageTitle} rightComponent={false}>
      <BaseLayout.Content>
        <ScrollView contentContainerStyle={styles.content}>
          {sections.map((section) => (
            <SettingSection
              key={section.group}
              title={trans[section.group]}
              testID={`settings-section-${section.group}`}
            >
              {section.fields.map(({ field: l, index: i }) => {
                const itemTitle = nonEnglish ? i18n.transform(lang, l)?.label : l.label;
                const editable = l.editable && l.type !== 'switch';
                return (
                  <SettingRow
                    key={l.id}
                    label={itemTitle}
                    description={describe(l.description)}
                    control={getControl(l)}
                    value={renderValue(l)}
                    level={{ kind: l.levelKind, value: settingsState?.[l.name] }}
                    onPress={editable ? () => handleEditPress(l.id) : null}
                    onValueChange={(value) => handleOnSwitch(value, l.key)}
                    testID={`settings-form-item-${i}`}
                    switchTestID={`settings-form-switch-${i}`}
                  />
                );
              })}
            </SettingSection>
          ))}
          {curConfig?.note && (
            <View style={styles.note}>
              <MessageNote lines={[trans[curConfig.note]]} testID="settings-note" />
            </View>
          )}
        </ScrollView>
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
  content: {
    paddingTop: 8,
    paddingBottom: 16,
  },
  note: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
});

export default SettingsForm;
