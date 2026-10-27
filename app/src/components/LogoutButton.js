import React, { useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Button } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import { useNavigation } from '@react-navigation/native';
import { AuthState, UserState, FormState, UIState, DatapointSyncState } from '../store';
import { api, cascades, i18n } from '../lib';
import { openDatabase } from '../database';
import sql from '../database/sql';
import useTheme from '../lib/theme';
import ConfirmDialog from './ConfirmDialog';

const LogoutButton = () => {
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigation = useNavigation();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const theme = useTheme();

  const handleNoPress = () => {
    setVisible(false);
  };

  const handleYesPress = async () => {
    setLoading(true);
    const db = await openDatabase();
    const tables = [
      'sessions',
      'users',
      'forms',
      'config',
      'datapoints',
      'jobs',
      'datapoint_sync_queue',
      'geometry_index',
    ];
    await Promise.all(
      tables.map(async (table) => {
        await sql.truncateTable(db, table);
      }),
    );
    AuthState.update((s) => {
      s.token = null;
    });
    UserState.update((s) => {
      s.id = null;
      s.name = null;
    });
    setLoading(false);
    setVisible(false);

    FormState.update((s) => {
      s.form = {};
      s.currentValues = {};
      s.visitedQuestionGroup = [];
      s.cascades = {};
      s.surveyDuration = 0;
    });

    DatapointSyncState.update((s) => {
      s.added = false;
      s.inProgress = false;
      s.progress = 0;
      s.completed = false;
      s.syncingFormId = null;
      s.formProgress = {};
    });

    UIState.update((s) => {
      s.statusBar = null;
    });

    await cascades.dropFiles();
    await db.closeAsync();
    api.setToken(null);

    navigation.navigate('GetStarted');
  };

  return (
    <View style={styles.container}>
      <Button
        title={trans.buttonReset}
        onPress={() => setVisible(true)}
        testID="list-item-logout"
        icon={
          <Icon
            name="log-out-outline"
            size={18}
            color={theme.buttonPrimary.text}
            style={styles.icon}
          />
        }
        buttonStyle={[styles.button, { backgroundColor: theme.status.error }]}
        titleStyle={[styles.title, { color: theme.buttonPrimary.text }]}
      />
      <Text style={[styles.caption, { color: theme.text.secondary }]}>
        {trans.settingsResetDesc}
      </Text>
      <ConfirmDialog
        visible={visible}
        title={`${trans.buttonReset}?`}
        message={trans.confirmReset}
        testID="dialog-confirm-logout"
        danger
        onClose={handleNoPress}
        actions={
          loading
            ? []
            : [
                {
                  label: trans.buttonCancel,
                  type: 'secondary',
                  onPress: handleNoPress,
                  testID: 'dialog-button-no',
                },
                {
                  label: trans.buttonReset,
                  type: 'primary',
                  onPress: handleYesPress,
                  testID: 'dialog-button-yes',
                },
              ]
        }
      >
        {loading && <ActivityIndicator style={{ marginVertical: 16 }} />}
      </ConfirmDialog>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    gap: 8,
  },
  button: {
    borderRadius: 24,
    paddingVertical: 14,
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
  },
  icon: {
    marginRight: 8,
  },
  caption: {
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
    paddingHorizontal: 8,
  },
});

export default LogoutButton;
