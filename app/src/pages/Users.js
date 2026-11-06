import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, BackHandler } from 'react-native';
import { Button } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout, LogoutButton, SettingSection } from '../components';
import { UserState, UIState, BuildParamsState } from '../store';
import { i18n } from '../lib';
import { crudUsers } from '../database/crud';
import useTheme from '../lib/theme';

const Users = ({ navigation }) => {
  const theme = useTheme();
  const [activeUser, setActiveUser] = useState(null);
  const { name, syncWifiOnly } = UserState.useState((s) => s);
  const activeLang = UIState.useState((s) => s.lang);
  const serverURL = BuildParamsState.useState((s) => s.serverURL);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const loadActiveUser = useCallback(async () => {
    const row = await crudUsers.getActiveUser(db);
    setActiveUser(row || null);
  }, [db]);

  useEffect(() => {
    loadActiveUser();
  }, [loadActiveUser]);

  useEffect(() => {
    const handleBackPress = () => {
      navigation.navigate('Home');
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', handleBackPress);
    return () => {
      backHandler.remove();
    };
  }, [navigation]);

  const lastSynced = activeUser?.lastSyncedAt
    ? new Date(activeUser.lastSyncedAt).toLocaleString()
    : trans.profileNeverSynced;
  // Passcode is shown so the operator can tell apart accounts that share a name
  const rows = [
    { key: 'name', label: trans.userLabel, value: name || '-' },
    { key: 'passcode', label: trans.passcodeLabel, value: activeUser?.password || '-' },
    { key: 'synced', label: trans.syncedLabel, value: lastSynced },
    {
      key: 'wifi',
      label: trans.syncWifiOnlyLabel,
      value: syncWifiOnly ? trans.buttonYes : trans.buttonNo,
    },
    { key: 'server', label: trans.serverLabel, value: serverURL || '-' },
  ];

  return (
    <BaseLayout
      title={trans.profilePageTitle}
      leftComponent={
        <Button type="clear" onPress={() => navigation.navigate('Home')} testID="arrow-back-button">
          <Icon name="arrow-back" size={18} color={theme.topNav.icon} />
        </Button>
      }
      rightComponent={false}
    >
      <BaseLayout.Content>
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.profileHeader} testID="profile-header">
            <Icon name="person-circle-outline" size={72} color={theme.icon.secondary} />
            <Text style={[styles.profileName, { color: theme.text.primary }]} testID="profile-name">
              {name || '-'}
            </Text>
          </View>
          <SettingSection testID="profile-info">
            {rows.map((row) => (
              <View
                key={row.key}
                style={[styles.infoRow, { borderBottomColor: theme.border.divider }]}
                testID={`profile-row-${row.key}`}
              >
                <Text style={[styles.infoLabel, { color: theme.text.secondary }]}>{row.label}</Text>
                <Text
                  style={[styles.infoValue, { color: theme.text.primary }]}
                  selectable={row.key === 'passcode'}
                  testID={`profile-value-${row.key}`}
                >
                  {row.value}
                </Text>
              </View>
            ))}
          </SettingSection>
          <SettingSection testID="profile-logout">
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
  profileHeader: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  profileName: {
    marginTop: 8,
    fontSize: 18,
    fontWeight: 'bold',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  infoLabel: {
    fontSize: 14,
  },
  infoValue: {
    fontWeight: '500',
    flexShrink: 1,
    textAlign: 'right',
    marginLeft: 12,
    fontSize: 14,
  },
});

export default Users;
