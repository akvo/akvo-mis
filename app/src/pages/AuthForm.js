import React, { useState, useMemo } from 'react';
import {
  View,
  StyleSheet,
  Platform,
  ToastAndroid,
  TouchableOpacity,
  Text,
  TextInput,
  StatusBar,
  ActivityIndicator,
  KeyboardAvoidingView,
  ScrollView,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';

import { api, cascades, i18n } from '../lib';
import { AuthState, UserState, UIState, BuildParamsState } from '../store';
import { crudForms, crudUsers, crudConfig } from '../database/crud';
import useTheme from '../lib/theme';

const AuthForm = () => {
  const theme = useTheme();
  const { online: isNetworkAvailable, lang: activeLang } = UIState.useState((s) => s);
  const { appVersion, serverURL } = BuildParamsState.useState((s) => s);
  const [passcode, setPasscode] = useState(null);
  const [hidden, setHidden] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showServerURL, setShowServerURL] = useState(false);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const disableLoginButton = useMemo(() => !passcode || passcode === '', [passcode]);

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
    console.info('[AuthForm] Downloading forms:', formsUrl?.length, formsUrl);
    const formsReq = formsUrl?.map((f) => api.get(f.url));
    const formsRes = await Promise.allSettled(formsReq);
    const failed = formsRes.filter((r) => r.status === 'rejected');
    if (failed.length) {
      console.error('[AuthForm] Form download failures:', failed.map((r) => r.reason?.message));
    }
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
        const bearerToken = data.syncToken;
        api.setToken(bearerToken);

        await crudConfig.updateConfig(db, { authenticationCode: passcode });
        await cascades.createSqliteDir();

        const userID = await handleActiveUser({
          ...data,
          passcode,
        });

        await handleGetAllForms(data.formsUrl, userID);

        // Set the token AFTER forms are downloaded. This triggers
        // RootNavigator to switch from auth screens to app screens,
        // unmounting AuthForm — anything after this line may not run.
        AuthState.update((s) => {
          s.authenticationCode = passcode;
          s.token = bearerToken;
        });
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

  const hasError = !!error;

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: theme.bg.surfacePrimary }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <StatusBar
        barStyle={theme.statusBar.style === 'light' ? 'light-content' : 'dark-content'}
        backgroundColor={theme.statusBar.bg}
      />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.headerBlock}>
          <Text style={[styles.headerTitle, { color: theme.text.primary }]}>
            {trans.authTitle1}
          </Text>
          <Text style={[styles.headerTitle, { color: theme.text.primary }]}>
            {trans.authTitle2}
          </Text>
          <Text style={[styles.headerTitle, { color: theme.text.primary }]}>
            {trans.authTitle3}
          </Text>
          <Text style={[styles.headerSubtitle, { color: theme.text.secondary }]}>
            {trans.authCaseSensitive}
          </Text>
        </View>

        <View style={styles.formBlock}>
          <View
            style={[
              styles.inputContainer,
              {
                backgroundColor: theme.input.bg,
                borderColor: hasError ? theme.input.errorBorder : 'transparent',
              },
            ]}
          >
            <TextInput
              style={[styles.input, { color: theme.input.textInput }]}
              placeholder={trans.authInputPasscode}
              placeholderTextColor={theme.input.text}
              secureTextEntry={hidden}
              autoFocus
              maxLength={8}
              value={passcode}
              onChangeText={setPasscode}
              testID="auth-password-field"
            />
            <TouchableOpacity
              onPress={() => setHidden(!hidden)}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              testID="auth-toggle-eye-button"
            >
              <Icon
                name={hidden ? 'eye-outline' : 'eye-off-outline'}
                size={22}
                color={theme.text.tertiary}
              />
            </TouchableOpacity>
          </View>

          {hasError && (
            <View>
              <Text style={[styles.errorText, { color: theme.input.errorText }]} testID="auth-error-text">
                {error}
              </Text>
              <View
                style={[
                  styles.tipsContainer,
                  { backgroundColor: theme.isDark ? theme.bg.surfaceElevated2 : '#FEF2F2' },
                ]}
              >
                <View style={styles.tipsHeader}>
                  <Icon name="alert-circle" size={16} color={theme.status.error} />
                  <Text style={[styles.tipsTitle, { color: theme.status.error }]}>
                    {trans.authErrorTipsTitle}
                  </Text>
                </View>
                <View style={styles.tipsList}>
                  <Text style={[styles.tipItem, { color: theme.text.secondary }]}>
                    {'\u2022  '}{trans.authErrorTip1}
                  </Text>
                  <Text style={[styles.tipItem, { color: theme.text.secondary }]}>
                    {'\u2022  '}{trans.authErrorTip2}
                  </Text>
                  <Text style={[styles.tipItem, { color: theme.text.secondary }]}>
                    {'\u2022  '}{trans.authErrorTip3}
                  </Text>
                  <Text style={[styles.tipItem, { color: theme.text.secondary }]}>
                    {'\u2022  '}{trans.authErrorTip4}
                  </Text>
                </View>
              </View>
            </View>
          )}
        </View>

        <TouchableOpacity onPress={() => setShowServerURL(!showServerURL)}>
          <Text style={[styles.versionText, { color: theme.text.tertiary }]}>
            App version - {appVersion}
          </Text>
        </TouchableOpacity>
        {showServerURL && (
          <Text style={[styles.serverURLText, { color: theme.text.tertiary }]}>
            {serverURL || 'No server URL configured'}
          </Text>
        )}
      </ScrollView>

      <View
        style={[
          styles.buttonBar,
          {
            backgroundColor: theme.bg.surfaceElevated3,
            borderTopColor: theme.border.listDivider,
          },
        ]}
      >
        <TouchableOpacity
          style={[
            styles.loginButton,
            {
              backgroundColor: disableLoginButton || loading
                ? theme.buttonPrimary.bgDisabled
                : theme.buttonPrimary.bg,
            },
          ]}
          onPress={handleOnPressLogin}
          disabled={disableLoginButton || loading}
          activeOpacity={0.8}
          testID="auth-login-button"
        >
          {loading ? (
            <ActivityIndicator color={theme.buttonPrimary.text} testID="auth-loading" />
          ) : (
            <Text
              style={[
                styles.loginButtonText,
                {
                  color: disableLoginButton
                    ? theme.buttonPrimary.textDisabled
                    : theme.buttonPrimary.text,
                },
              ]}
            >
              {trans.buttonLogin}
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 80,
    paddingBottom: 24,
    justifyContent: 'center',
    gap: 24,
  },
  headerBlock: {
    gap: 2,
  },
  headerTitle: {
    fontSize: 30,
    fontWeight: '500',
    lineHeight: 38,
  },
  headerSubtitle: {
    fontSize: 18,
    fontWeight: '400',
    lineHeight: 26,
    marginTop: 8,
  },
  formBlock: {
    gap: 6,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    height: 52,
  },
  input: {
    flex: 1,
    fontSize: 16,
    height: '100%',
  },
  errorText: {
    fontSize: 13,
    fontWeight: '500',
    marginTop: 6,
  },
  tipsContainer: {
    marginTop: 12,
    padding: 14,
    borderRadius: 12,
  },
  tipsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  tipsTitle: {
    fontSize: 13,
    fontWeight: '600',
  },
  tipsList: {
    gap: 4,
  },
  tipItem: {
    fontSize: 13,
    lineHeight: 18,
  },
  buttonBar: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 20,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
  },
  loginButton: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 16,
  },
  loginButtonText: {
    fontSize: 18,
    fontWeight: '600',
  },
  versionText: {
    textAlign: 'center',
    fontSize: 12,
  },
  serverURLText: {
    textAlign: 'center',
    fontSize: 12,
  },
});

export default AuthForm;
