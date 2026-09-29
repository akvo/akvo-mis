import React from 'react';
import { ScrollView, StyleSheet } from 'react-native';

import { BaseLayout, LogoutButton, SettingRow, SettingSection } from '../components';
import { config } from './Settings/config';
import { UIState, BuildParamsState } from '../store';
import { i18n } from '../lib';

const darkModeOptions = ['auto', 'light', 'dark'];
const darkModeLabels = { auto: 'appearanceAuto', light: 'appearanceLight', dark: 'appearanceDark' };

const Settings = ({ navigation }) => {
  const activeLang = UIState.useState((s) => s.lang);
  const darkModePreference = UIState.useState((s) => s.darkModePreference) || 'auto';
  const trans = i18n.text(activeLang);
  const nonEnglish = activeLang !== 'en';
  const authenticationType = BuildParamsState.useState((s) => s.authenticationType);

  const handleCycleDarkMode = () => {
    const nextIndex = (darkModeOptions.indexOf(darkModePreference) + 1) % darkModeOptions.length;
    UIState.update((s) => {
      s.darkModePreference = darkModeOptions[nextIndex];
    });
  };

  const goToForm = (id) => {
    const findConfig = config.find((c) => c?.id === id);
    navigation.navigate('SettingsForm', { id, name: findConfig?.name });
  };

  return (
    <BaseLayout title={trans.settingsPageTitle} rightComponent={false}>
      <BaseLayout.Content>
        <ScrollView contentContainerStyle={styles.content}>
          <SettingSection title={trans.settingsApplication} testID="settings-section-application">
            {config.map((c, i) => (
              <SettingRow
                key={c.id}
                icon={c.icon}
                label={nonEnglish ? i18n.transform(activeLang, c)?.name : c.name}
                onPress={() => goToForm(c.id)}
                testID={`goto-settings-form-${i}`}
              />
            ))}
            {/* Show this only if no code_assignment in auth type */}
            {!authenticationType.includes('code_assignment') && (
              <SettingRow
                icon="add-circle-outline"
                label={trans.settingAddFormTitle}
                onPress={() => navigation.navigate('AddNewForm', {})}
                testID="add-more-forms"
              />
            )}
            <SettingRow
              icon="language-outline"
              label={trans.langTitle}
              onPress={() => navigation.navigate('Language')}
              testID="settings-language"
            />
            <SettingRow
              icon="contrast-outline"
              label={trans.appearance}
              description={trans[darkModeLabels[darkModePreference]]}
              onPress={handleCycleDarkMode}
              testID="dark-mode-toggle"
            />
            <SettingRow
              icon="help-circle-outline"
              label={trans.about}
              onPress={() => navigation.navigate('About')}
              testID="settings-about"
            />
          </SettingSection>
          <SettingSection title={trans.settingsDataReset} testID="settings-section-data-reset">
            <LogoutButton />
          </SettingSection>
        </ScrollView>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  content: {
    paddingTop: 8,
    paddingBottom: 16,
  },
});

export default Settings;
