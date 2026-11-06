import React from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Text,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { BaseLayout, ConfirmDialog, SettingRow, SettingSection } from '../../components';
import { BuildParamsState, UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';
import useVersionCheck from '../../hooks/use-version-check';

const AboutHome = () => {
  const { appVersion, apkName } = BuildParamsState.useState((s) => s);
  const isOnline = UIState.useState((s) => s.online);
  const { lang } = UIState.useState((s) => s);
  const trans = i18n.text(lang);
  const theme = useTheme();
  const { visible, setVisible, checking, updateInfo, checkVersion, handleUpdate } =
    useVersionCheck();
  const updateColor = isOnline ? theme.buttonGhost.color : theme.buttonGhost.colorDisabled;

  return (
    <BaseLayout title={trans.about} rightComponent={false}>
      <BaseLayout.Content>
        <ScrollView contentContainerStyle={styles.content}>
          <SettingSection>
            <SettingRow
              label={`${trans.about} ${apkName}`}
              description={trans.aboutAppDescription}
              control="none"
            />
            <SettingRow label={trans.appVersionLabel} control="value" value={appVersion} />
          </SettingSection>
        </ScrollView>

        {/* Figma "Check app update" (6499:17856): ghost button pinned to the bottom */}
        <View style={styles.bottomBar}>
          <TouchableOpacity
            style={styles.updateButton}
            onPress={() => checkVersion()}
            disabled={!isOnline}
            testID="update-button"
            accessibilityRole="button"
            accessibilityState={{ disabled: !isOnline }}
          >
            <Icon name="refresh" size={24} color={updateColor} />
            <Text style={[styles.updateButtonText, { color: updateColor }]}>
              {trans.checkAppUpdate}
            </Text>
          </TouchableOpacity>
        </View>

        <ConfirmDialog
          visible={visible}
          title={checking ? trans.checkingVersion : null}
          message={checking ? null : updateInfo.text}
          onClose={() => setVisible(false)}
          actions={
            checking
              ? []
              : [
                  ...(updateInfo.status === 200
                    ? [
                        {
                          label: trans.buttonUpdate,
                          type: 'primary',
                          onPress: handleUpdate,
                        },
                      ]
                    : []),
                  {
                    label: trans.buttonCancel,
                    type: 'secondary',
                    onPress: () => setVisible(false),
                  },
                ]
          }
        >
          {checking && <ActivityIndicator style={styles.loading} color={theme.buttonPrimary.bg} />}
        </ConfirmDialog>
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  content: {
    paddingTop: 8,
  },
  bottomBar: {
    paddingTop: 8,
    paddingBottom: 16,
    paddingHorizontal: 16,
  },
  updateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 16,
  },
  updateButtonText: {
    fontSize: 16,
    fontWeight: '700',
    lineHeight: 24,
  },
  loading: {
    marginVertical: 16,
  },
});

export default AboutHome;
