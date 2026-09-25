import React, { useState } from 'react';
import { View, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Text, Icon } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';
import { AuthState, UserState, FormState, UIState, DatapointSyncState } from '../store';
import { api, cascades, i18n } from '../lib';
import { openDatabase } from '../database';
import sql from '../database/sql';
import useTheme from '../lib/theme';
import ConfirmDialog from './ConfirmDialog';

const LogoutButton = () => {
  const theme = useTheme();
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigation = useNavigation();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

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
      s.draftInProgress = false;
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
    <View>
      <TouchableOpacity
        onPress={() => setVisible(true)}
        testID="list-item-logout"
        style={[styles.listItem, { backgroundColor: theme.bg.surfaceSecondary, borderBottomColor: theme.border.listDivider }]}
      >
        <View style={styles.contentContainer}>
          <Text style={[styles.buttonText, { color: theme.text.primary }]}>{trans.buttonReset}</Text>
        </View>
        <Icon name="refresh" type="ionicon" color={theme.icon.secondary} size={24} />
      </TouchableOpacity>
      <ConfirmDialog
        visible={visible}
        title={trans.confirmResetTitle || 'Reset application?'}
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
                  label: `${trans.buttonYes}, reset`,
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

export default LogoutButton;

const styles = StyleSheet.create({
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  contentContainer: {
    flex: 1,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '500',
  },
});
