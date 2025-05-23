import React, { useState } from 'react';
import { View, TouchableOpacity, StyleSheet } from 'react-native';
import { Dialog, Text, Icon } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';
import * as SQLite from 'expo-sqlite';
import { AuthState, UserState, FormState, UIState } from '../store';
import { api, cascades, i18n } from '../lib';
import { DATABASE_NAME } from '../lib/constants';
import sql from '../database/sql';

const LogoutButton = () => {
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigation = useNavigation();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const handleNoPress = () => {
    setVisible(false);
  };

  const handleYesPress = async () => {
    const db = await SQLite.openDatabaseAsync(DATABASE_NAME, {
      useNewConnection: true,
    });
    const tables = ['sessions', 'users', 'forms', 'config', 'datapoints', 'jobs'];
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
      s.currentValues = {}; // answers
      s.visitedQuestionGroup = [];
      s.cascades = {};
      s.surveyDuration = 0;
    });

    /**
     * Remove sqlite files
     */
    await cascades.dropFiles();
    await db.closeAsync();
    /**
     * Reset axios token
     */
    api.setToken(null);

    navigation.navigate('GetStarted');
  };

  return (
    <View>
      <TouchableOpacity
        onPress={() => setVisible(true)}
        testID="list-item-logout"
        style={styles.listItem}
      >
        <View style={styles.contentContainer}>
          <Text style={styles.buttonText}>{trans.buttonReset}</Text>
        </View>
        <Icon name="refresh" type="ionicon" color="grey" size={24} />
      </TouchableOpacity>
      <Dialog testID="dialog-confirm-logout" isVisible={visible}>
        {loading ? <Dialog.Loading /> : <Text>{trans.confirmReset}</Text>}
        <Dialog.Actions>
          <Dialog.Button onPress={handleYesPress} testID="dialog-button-yes">
            {trans.buttonYes}
          </Dialog.Button>
          <Dialog.Button onPress={handleNoPress} testID="dialog-button-no">
            {trans.buttonNo}
          </Dialog.Button>
        </Dialog.Actions>
      </Dialog>
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
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  contentContainer: {
    flex: 1,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#212121',
  },
});
