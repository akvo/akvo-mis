/* eslint-disable no-console */
import React from 'react';
import { View, StyleSheet, Platform, ToastAndroid } from 'react-native';
import { Input, Button, Text } from '@rneui/themed';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';

import { CenterLayout, LogoImage } from '../components';
import { api, cascades, i18n } from '../lib';
import { AuthState, UserState, UIState } from '../store';
import { crudSessions, crudForms, crudUsers } from '../database/crud';
import useTheme from '../lib/theme';

const AuthByPassForm = ({ navigation }) => {
  const theme = useTheme();
  const { online: isNetworkAvailable, lang: activeLang } = UIState.useState((s) => s);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [formId, setFormId] = React.useState(null);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const goTo = (page) => navigation.navigate(page);

  const handleDownloadForm = () => {
    if (!isNetworkAvailable) {
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.authErrorNoConn, ToastAndroid.LONG);
      }
      return;
    }
    setLoading(true);
    setError(null);
    api
      .get(`/forms/${formId}`)
      .then(async (res) => {
        try {
          const { data } = res;
          // save session
          const bearerToken = 'NO TOKEN';
          const lastSession = await crudSessions.selectLastSession(db);
          if (!lastSession && lastSession?.token !== bearerToken) {
            await crudSessions.addSession(db, { token: bearerToken, passcode: 'NO PASSCODE' });
          }
          await cascades.createSqliteDir();
          // save forms
          await crudForms.upsertForm(db, {
            id: data.id,
            version: data.version,
            formJSON: data,
          });
          // download cascades files
          if (data?.cascades?.length) {
            data.cascades.forEach((cascadeFile) => {
              const downloadUrl = api.getConfig().baseURL + cascadeFile;
              cascades.download(downloadUrl, cascadeFile);
            });
          }
          // check users exist
          const activeUser = await crudUsers.getActiveUser(db);
          // update auth state
          AuthState.update((s) => {
            s.authenticationCode = 'NO PASSCODE';
            s.token = bearerToken;
          });
          if (!activeUser || !activeUser?.id) {
            goTo('AddUser');
          } else {
            UserState.update((s) => {
              s.id = activeUser?.id;
              s.name = activeUser?.name;
            });
            goTo('Home');
          }
        } catch (err) {
          Sentry.captureMessage(
            `[AuthByPassForm] Unable to store session, activeUser & redirect to Homepage`,
          );
          Sentry.captureException(err);
        }
      })
      .catch((err) => {
        const { status: errStatus } = err?.response || {};
        if ([400, 401].includes(errStatus)) {
          setError(trans.authErrorPasscode);
        } else {
          setError(err?.message);
        }
      })
      .finally(() => setLoading(false));
  };

  return (
    <CenterLayout>
      <LogoImage />
      {loading ? (
        <View>
          <Text style={[styles.dialogLoadingText, { color: theme.text.secondary }]}>
            {trans.fetchingData}
          </Text>
        </View>
      ) : (
        <View>
          <Input
            placeholder={trans.inputFormID}
            testID="input-form-id"
            autoFocus
            value={formId}
            onChangeText={setFormId}
            keyboardType="numeric"
            inputContainerStyle={styles.inputFormId}
          />
          <Button testID="button-download-form" onPress={handleDownloadForm}>
            {trans.downloadFormButton}
          </Button>
        </View>
      )}
      {error && (
        <Text style={[styles.errorText, { color: theme.status.error }]} testID="fetch-error-text">
          {error}
        </Text>
      )}
    </CenterLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    paddingHorizontal: 16,
  },
  text: {
    marginLeft: 8,
  },
  dialogLoadingContainer: {
    flex: 1,
  },
  dialogLoadingText: {
    textAlign: 'center',
    fontStyle: 'italic',
  },
  inputFormId: {
    width: '75%',
  },
  errorText: { fontStyle: 'italic', marginHorizontal: 10, marginTop: -8 },
});

export default AuthByPassForm;
