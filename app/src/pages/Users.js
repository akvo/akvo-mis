import React, { useState, useEffect, useCallback } from 'react';
import {
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Platform,
  ToastAndroid,
  BackHandler,
} from 'react-native';
import { Button, Skeleton } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSQLiteContext } from 'expo-sqlite';
import { BaseLayout } from '../components';
import { UserState, UIState, AuthState } from '../store';
import { api, i18n } from '../lib';
import { crudConfig, crudUsers } from '../database/crud';
import useTheme from '../lib/theme';

const Users = ({ navigation, route }) => {
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState([]);
  const currUserID = UserState.useState((s) => s.id);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const loadUsers = useCallback(async () => {
    const rows = await crudUsers.getAllUsers(db);
    setUsers(rows);
    setLoading(false);
  }, [db]);

  const handleSelectUser = async ({ id, name, password, token }) => {
    await crudUsers.toggleActive(db, { id: currUserID, active: 1 });
    await crudUsers.toggleActive(db, { id, active: 0 });
    await crudConfig.updateConfig(db, { authenticationCode: password });
    api.setToken(token);

    AuthState.update((s) => {
      s.token = token;
    });
    UserState.update((s) => {
      s.id = id;
      s.name = name;
    });
    await loadUsers();

    if (Platform.OS === 'android') {
      ToastAndroid.show(`${trans.usersSwitchTo}${name}`, ToastAndroid.SHORT);
    }
  };

  useEffect(() => {
    if (loading) {
      loadUsers();
    }
    if (!loading && route?.params?.added) {
      const newUser = route.params.added;
      const findNew = users.find((u) => u.id === newUser?.id);
      if (!findNew) {
        setLoading(true);
      }
    }
  }, [loading, route, loadUsers, users]);

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

  return (
    <BaseLayout
      title={trans.usersPageTitle}
      leftComponent={
        <Button type="clear" onPress={() => navigation.navigate('Home')} testID="arrow-back-button">
          <Icon name="arrow-back" size={18} color={theme.topNav.icon} />
        </Button>
      }
      rightComponent={false}
    >
      {loading ? (
        <Skeleton animation="wave" testID="loading-users" />
      ) : (
        <FlatList
          data={users}
          keyExtractor={(user) => user.id.toString()}
          style={styles.listContainer}
          testID="users-list"
          renderItem={({ item: user }) => (
            <TouchableOpacity
              onPress={() => handleSelectUser(user)}
              testID={`list-item-user-${user.id}`}
              style={[styles.userItem, { borderBottomColor: theme.border.listDivider }]}
            >
              <Text testID={`title-username-${user.id}`} style={{ color: theme.text.primary }}>{user.name}</Text>
              {user.active === 1 && (
                <Icon name="checkmark" size={18} color={theme.status.success} testID={`icon-checkmark-${user.id}`} />
              )}
            </TouchableOpacity>
          )}
        />
      )}
    </BaseLayout>
  );
};

const styles = StyleSheet.create({
  listContainer: {
    width: '100%',
    flex: 1,
  },
  userItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: undefined,
  },
});

export default Users;
