import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, BackHandler } from 'react-native';
import { Button, Divider } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout, LogoutButton } from '../components';
import { UserState, UIState, BuildParamsState } from '../store';
import { i18n } from '../lib';
import { crudUsers } from '../database/crud';

const Users = ({ navigation }) => {
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
    { key: 'synced', label: trans.syncLabel, value: lastSynced },
    { key: 'wifi', label: trans.syncWifiOnlyLabel, value: syncWifiOnly ? trans.buttonYes : trans.buttonNo },
    { key: 'server', label: trans.serverLabel, value: serverURL || '-' },
  ];

  return (
    <BaseLayout
      title={trans.profilePageTitle}
      leftComponent={
        <Button type="clear" onPress={() => navigation.navigate('Home')} testID="arrow-back-button">
          <Icon name="arrow-back" size={18} />
        </Button>
      }
      rightComponent={false}
    >
      <BaseLayout.Content>
        <View style={styles.profileHeader} testID="profile-header">
          <Icon name="person-circle-outline" size={72} color="#9ca3af" />
          <Text style={styles.profileName} testID="profile-name">
            {name || '-'}
          </Text>
        </View>
        <Divider width={8} color="#f9fafb" />
        {rows.map((row) => (
          <View key={row.key} style={styles.infoRow} testID={`profile-row-${row.key}`}>
            <Text style={styles.infoLabel}>{row.label}</Text>
            <Text
              style={styles.infoValue}
              selectable={row.key === 'passcode'}
              testID={`profile-value-${row.key}`}
            >
              {row.value}
            </Text>
          </View>
        ))}
        <Divider width={8} color="#f9fafb" />
        <LogoutButton />
      </BaseLayout.Content>
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  profileHeader: {
    alignItems: 'center',
    paddingVertical: 24,
    backgroundColor: 'white',
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
    paddingHorizontal: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  infoLabel: {
    color: '#666',
  },
  infoValue: {
    fontWeight: '500',
    flexShrink: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
});

export default Users;
