import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout, MessageNote } from '../../components';
import { FormState, UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';
import { crudConfig } from '../../database/crud';
import { langConfig } from './config';

// Figma F4 · Language (APP-487 D-4). Picking a language switches both the interface
// (UIState) and the question text of translated forms (FormState, A13).
const Language = () => {
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const theme = useTheme();
  const db = useSQLiteContext();

  const handleSelect = async (value) => {
    UIState.update((s) => {
      s.lang = value;
    });
    FormState.update((s) => {
      s.lang = value;
    });
    try {
      await crudConfig.updateConfig(db, { lang: value });
    } catch (err) {
      Sentry.captureException(err);
    }
  };

  return (
    <BaseLayout title={trans.langTitle} rightComponent={false}>
      <BaseLayout.Content>
        <ScrollView>
          {langConfig.options.map((option) => {
            const checked = option.value === activeLang;
            return (
              <TouchableOpacity
                key={option.value}
                style={styles.row}
                onPress={() => handleSelect(option.value)}
                testID={`language-option-${option.value}`}
                accessibilityRole="radio"
                accessibilityState={{ checked }}
              >
                <Text style={[styles.label, { color: theme.text.primary }]}>{option.label}</Text>
                <View
                  style={[
                    styles.checkbox,
                    checked
                      ? {
                          backgroundColor: theme.buttonPrimary.bg,
                          borderColor: theme.buttonPrimary.bg,
                        }
                      : { borderColor: theme.icon.secondary },
                  ]}
                >
                  {checked && <Icon name="checkmark" size={16} color={theme.buttonPrimary.text} />}
                </View>
                <View style={[styles.divider, { backgroundColor: theme.border.divider }]} />
              </TouchableOpacity>
            );
          })}
          <View style={styles.note}>
            <MessageNote lines={[trans.languageNote]} testID="settings-note" />
          </View>
        </ScrollView>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    minHeight: 56,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  label: {
    flex: 1,
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 24,
    letterSpacing: 0.5,
  },
  // 18px box in a 40px touch area, as the Figma checkbox
  checkbox: {
    width: 18,
    height: 18,
    margin: 11,
    borderWidth: 2,
    borderRadius: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  divider: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 0,
    height: 1,
  },
  note: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
});

export default Language;
