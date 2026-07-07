import React, { useState } from 'react';
import Icon from 'react-native-vector-icons/Ionicons';
import { View, StyleSheet, Platform, ToastAndroid, TouchableOpacity } from 'react-native';
import { Input, Button, Text } from '@rneui/themed';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';

import { CenterLayout, LogoImage } from '../components';
import { api, cascades, i18n } from '../lib';
import { AuthState, UserState, UIState, BuildParamsState } from '../store';
import { crudForms, crudUsers, crudConfig } from '../database/crud';

const ToggleEye = ({ hidden, onPress }) => {
  const iconName = hidden ? 'eye' : 'eye-off';
  return (
    <Button type="clear" onPress={onPress} testID="auth-toggle-eye-button">
      <Icon name={iconName} size={24} />
    </Button>
  );
};

const AuthForm = ({ navigation }) => {
  const { online: isNetworkAvailable, lang: activeLang } = UIState.useState((s) => s);
  const { appVersion, serverURL } = BuildParamsState.useState((s) => s);
  const [passcode, setPasscode] = React.useState(null);
  const [hidden, setHidden] = React.useState(true);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [showServerURL, setShowServerURL] = useState(false);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const toggleHidden = () => setHidden(!hidden);

  const disableLoginButton = React.useMemo(() => !passcode || passcode === '', [passcode]);

  const handleActiveUser = async (data = {}) => {
    const activeUser = await crudUsers.getActiveUser(db);
    if (activeUser) {
      UserState.update((s) => {
        s.id = activeUser.id;
        s.name = activeUser.name;
      });
      return activeUser.id;
    }

    if (!activeUser?.id) {
      const newUserId = await crudUsers.addNew(db, {
        name: data?.name || 'Data collector',
        active: 1,
        token: data?.syncToken,
        password: data?.passcode,
      });
      UserState.update((s) => {
        s.id = newUserId;
        s.name = data?.name;
      });
      return newUserId;
    }

    return null;
  };

  const handleGetAllForms = async (formsUrl, userID) => {
    const formsReq = formsUrl?.map((f) => api.get(f.url));
    const formsRes = await Promise.allSettled(formsReq);
    await formsRes.reduce(async (prev, { value, status }, index) => {
      await prev;
      if (status === 'fulfilled') {
        const { data: apiData } = value;
        await Promise.allSettled(
          (apiData.cascades || []).map((cascadeFile) => {
            const downloadUrl = api.getConfig().baseURL + cascadeFile;
            return cascades.download(downloadUrl, cascadeFile);
          }),
        );
        const form = formsUrl?.[index];
        await crudForms.upsertForm(db, {
          ...form,
          userId: userID,
          formJSON: apiData,
        });
      }
    }, Promise.resolve());
  };

  const handleOnPressLogin = () => {
    // check connection
    if (!isNetworkAvailable) {
      if (Platform.OS === 'android') {
        ToastAndroid.show(trans.authErrorNoConn, ToastAndroid.LONG);
      }
      return;
    }
    setError(null);
    setLoading(true);
    api.setServerURL(serverURL);
    console.info('[AuthForm] Attempting login to:', serverURL);
    api
      .post('/auth', { code: passcode })
      .then(async (res) => {
        const { data } = res;
        // save session
        const bearerToken = data.syncToken;
        api.setToken(bearerToken);

        await crudConfig.updateConfig(db, { authenticationCode: passcode });
        await cascades.createSqliteDir();
        // update auth state
        AuthState.update((s) => {
          s.authenticationCode = passcode;
          s.token = bearerToken;
        });

        const userID = await handleActiveUser({
          ...data,
          passcode,
        });

        await handleGetAllForms(data.formsUrl, userID);

        // go to home page (form list)
        setTimeout(() => {
          navigation.navigate('Home', { newForms: true });
        }, 500);
      })
      .catch((err) => {
        console.error('[AuthForm] Login error:', {
          message: err?.message,
          code: err?.code,
          status: err?.response?.status,
          responseData: err?.response?.data,
          config: {
            url: err?.config?.url,
            baseURL: err?.config?.baseURL,
            method: err?.config?.method,
          },
        });
        const { status: errorCode } = err?.response || {};
        if ([400, 401].includes(errorCode)) {
          setError(`${errorCode}: ${trans.authErrorPasscode}`);
        } else {
          setError(`${errorCode}: ${err?.message}`);
          Sentry.captureMessage('[AuthForm] unable to sign-in with passcode');
          Sentry.captureException(err);
        }
      })
      .finally(() => setLoading(false));
  };

  const titles = [trans.authTitle1, trans.authTitle2, trans.authTitle3];
  return (
    <CenterLayout>
      <LogoImage />
      <CenterLayout.Titles items={titles} />
      <View style={styles.container}>
        <Input
          placeholder={trans.authInputPasscode}
          secureTextEntry={hidden}
          rightIcon={<ToggleEye hidden={hidden} onPress={toggleHidden} />}
          testID="auth-password-field"
          autoFocus
          value={passcode}
          onChangeText={setPasscode}
        />
        {error && (
          <Text style={styles.errorText} testID="auth-error-text">
            {error}
          </Text>
        )}
        <View>
          <Text style={styles.guidanceText}>The passcode is case sensitive</Text>
        </View>
      </View>
      <Button
        title="primary"
        disabled={disableLoginButton || loading}
        onPress={handleOnPressLogin}
        testID="auth-login-button"
      >
        {trans.buttonLogin}
      </Button>
      <TouchableOpacity onPress={() => setShowServerURL(!showServerURL)}>
        <Text style={styles.versionText}>App version - {appVersion}</Text>
      </TouchableOpacity>
      {showServerURL && (
        <Text style={styles.serverURLText}>{serverURL || 'No server URL configured'}</Text>
      )}
    </CenterLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    paddingHorizontal: 16,
  },
  checkbox: {
    backgroundColor: '#f9fafb',
  },
  text: {
    marginLeft: 8,
  },
  errorText: { color: 'red', fontStyle: 'italic', marginHorizontal: 10, marginTop: -8 },
  dialogLoadingContainer: {
    flex: 1,
  },
  dialogLoadingText: {
    textAlign: 'center',
    fontStyle: 'italic',
  },
  guidanceText: {
    textAlign: 'center',
    fontStyle: 'italic',
    color: '#CCCCCC',
  },
  versionText: {
    textAlign: 'center',
    color: '#999999',
    marginTop: 8,
  },
  serverURLText: {
    textAlign: 'center',
    color: '#666666',
    fontSize: 12,
    marginTop: 4,
  },
});

export default AuthForm;
