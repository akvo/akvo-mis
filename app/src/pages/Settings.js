import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Divider } from '@rneui/themed';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { BaseLayout, LogoutButton } from '../components';
import DialogForm from './Settings/DialogForm';
import { config, langConfig } from './Settings/config';
import { UIState, FormState, BuildParamsState } from '../store';
import { i18n } from '../lib';
import useTheme from '../lib/theme';

const Settings = ({ navigation }) => {
  const [showLang, setShowLang] = useState(false);
  const activeLang = UIState.useState((s) => s.lang);
  const darkModePreference = UIState.useState((s) => s.darkModePreference);
  const trans = i18n.text(activeLang);
  const theme = useTheme();
  const nonEnglish = activeLang !== 'en';
  const authenticationType = BuildParamsState.useState((s) => s.authenticationType);

  const darkModeOptions = ['auto', 'light', 'dark'];
  const handleCycleDarkMode = () => {
    const currentIndex = darkModeOptions.indexOf(darkModePreference || 'auto');
    const nextIndex = (currentIndex + 1) % darkModeOptions.length;
    UIState.update((s) => {
      s.darkModePreference = darkModeOptions[nextIndex];
    });
  };

  const handleSaveLang = (value) => {
    UIState.update((s) => {
      s.lang = value;
    });
    FormState.update((s) => {
      s.lang = value;
    });
    setShowLang(false);
  };

  const goToForm = (id) => {
    const findConfig = config.find((c) => c?.id === id);
    navigation.navigate('SettingsForm', { id, name: findConfig?.name });
  };

  const goToAddForm = () => {
    navigation.navigate('AddNewForm', {});
  };

  return (
    <BaseLayout title={trans.settingsPageTitle} rightComponent={false}>
      <BaseLayout.Content>
        <View>
          <Divider width={8} color="#f9fafb" />
          {config.map((c, i) => {
            const itemTitle = nonEnglish ? i18n.transform(activeLang, c)?.name : c.name;
            const itemDesc = nonEnglish
              ? i18n.transform(activeLang, c?.description)?.name
              : c?.description?.name;
            return (
              <TouchableOpacity
                key={c.id}
                onPress={() => goToForm(c.id)}
                testID={`goto-settings-form-${i}`}
                style={styles.listItem}
              >
                <View style={styles.listItemContent}>
                  <Text style={styles.listItemTitle}>{itemTitle}</Text>
                  <Text style={styles.listItemSubtitle}>{itemDesc}</Text>
                </View>
                <Icon name="chevron-right" size={24} color="#000" />
              </TouchableOpacity>
            );
          })}
          {/* Show this only if no code_assignment in auth type */}
          {!authenticationType.includes('code_assignment') && (
            <>
              <Divider width={8} color="#f9fafb" />
              <TouchableOpacity
                onPress={goToAddForm}
                testID="add-more-forms"
                style={styles.listItem}
              >
                <View style={styles.listItemContent}>
                  <Text style={styles.listItemTitle}>{trans.settingAddFormTitle}</Text>
                  <Text style={styles.listItemSubtitle}>{trans.settingAddFormDesc}</Text>
                </View>
                <Icon name="chevron-right" size={24} color="#000" />
              </TouchableOpacity>
            </>
          )}
          <Divider width={8} color={theme.bg.surfacePrimary} />
          <TouchableOpacity
            style={styles.listItem}
            onPress={handleCycleDarkMode}
            testID="dark-mode-toggle"
          >
            <View style={styles.listItemContent}>
              <Text style={[styles.listItemTitle, { color: theme.text.primary }]}>Appearance</Text>
              <Text style={[styles.listItemSubtitle, { color: theme.text.secondary }]}>
                {(darkModePreference || 'auto').charAt(0).toUpperCase() +
                  (darkModePreference || 'auto').slice(1)}
              </Text>
            </View>
            <Icon name="chevron-right" size={24} color={theme.icon?.primary || theme.text.primary} />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigation.navigate('About')} style={styles.listItem}>
            <View style={styles.listItemContent}>
              <Text style={[styles.listItemTitle, { color: theme.text.primary }]}>{trans.about}</Text>
            </View>
            <Icon name="chevron-right" size={24} color={theme.icon.primary} />
          </TouchableOpacity>
          <Divider width={8} color="#f9fafb" />
          <LogoutButton />
          <Divider width={8} color="#f9fafb" />
          <DialogForm
            onOk={handleSaveLang}
            onCancel={() => setShowLang(false)}
            showDialog={showLang}
            edit={langConfig}
            initValue={activeLang}
          />
        </View>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 12,
  },
  listItemContent: {
    flex: 1,
  },
  listItemTitle: {
    fontWeight: 'bold',
  },
  listItemSubtitle: {
    color: '#666',
  },
});

export default Settings;
