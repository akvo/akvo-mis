import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  StatusBar,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useSQLiteContext } from 'expo-sqlite';
import { BuildParamsState, UIState } from '../store';
import { api, i18n } from '../lib';
import { crudConfig } from '../database/crud';
import useTheme from '../lib/theme';
import heroImage from '../../assets/onboarding-hero.png';

const { height: SCREEN_H } = Dimensions.get('window');
const IMAGE_H = SCREEN_H * 0.55;

const GetStarted = ({ navigation }) => {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [currentConfig, setCurrentConfig] = useState({});
  const [IPAddr, setIPAddr] = useState(null);
  const serverURLState = BuildParamsState.useState((s) => s.serverURL);
  const authenticationType = BuildParamsState.useState((s) => s.authenticationType);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const db = useSQLiteContext();

  const getConfig = useCallback(async () => {
    const config = await crudConfig.getConfig(db);
    if (config) {
      setCurrentConfig(config);
    }
  }, [db]);

  const isServerURLDefined = useMemo(
    () => currentConfig?.serverURL || serverURLState,
    [currentConfig?.serverURL, serverURLState],
  );

  useEffect(() => {
    getConfig();
  }, [getConfig]);

  const goToLogin = async () => {
    if (IPAddr) {
      BuildParamsState.update((s) => {
        s.serverURL = IPAddr;
      });
      api.setServerURL(IPAddr);
      await crudConfig.updateConfig(db, { serverURL: IPAddr });
    }
    setTimeout(() => {
      if (authenticationType.includes('code_assignment')) {
        navigation.navigate('AuthForm');
        return;
      }
      navigation.navigate('AuthByPassForm');
    }, 100);
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg.surfacePrimary }]}>
      <StatusBar
        barStyle={theme.statusBar.style === 'light' ? 'light-content' : 'dark-content'}
        backgroundColor="transparent"
        translucent
      />
      <Image source={heroImage} style={styles.heroImage} resizeMode="cover" />

      <View
        style={[
          styles.textCard,
          { backgroundColor: theme.bg.surfaceElevated3 },
        ]}
      >
        <Text style={[styles.title, { color: theme.text.primary }]}>
          {trans.getStartedTitle1}
        </Text>
        <Text style={[styles.title, { color: theme.text.highlight }]}>
          {trans.getStartedTitle2}
        </Text>
        <Text style={[styles.title, { color: theme.text.primary }]}>
          {trans.getStartedTitle3}
        </Text>
        <Text style={[styles.subtitle, { color: theme.text.secondary }]}>
          {trans.getStartedSubTitle}
        </Text>
      </View>

      <View
        style={[
          styles.buttonBar,
          {
            backgroundColor: theme.bg.surfaceElevated3,
            borderTopColor: theme.border.listDivider,
            paddingBottom: Math.max(insets.bottom, 16),
          },
        ]}
      >
        {!isServerURLDefined && (
          <TextInput
            style={[
              styles.serverInput,
              {
                backgroundColor: theme.input.bg,
                borderColor: theme.input.border,
                color: theme.input.textInput,
              },
            ]}
            placeholder={trans.getStartedInputServer}
            placeholderTextColor={theme.input.text}
            onChangeText={setIPAddr}
            testID="server-url-field"
          />
        )}

        <TouchableOpacity
          style={[styles.button, { backgroundColor: theme.buttonPrimary.bg }]}
          onPress={goToLogin}
          activeOpacity={0.8}
          testID="get-started-button"
        >
          <Text style={[styles.buttonText, { color: theme.buttonPrimary.text }]}>
            {trans.buttonGetStarted}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    gap: 8,
  },
  heroImage: {
    width: '100%',
    height: IMAGE_H,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  textCard: {
    flex: 1,
    paddingHorizontal: 24,
    paddingVertical: 24,
    borderRadius: 24,
    justifyContent: 'center',
  },
  buttonBar: {
    paddingHorizontal: 24,
    paddingTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    gap: 12,
  },
  title: {
    fontSize: 36,
    fontWeight: '500',
    lineHeight: 44,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '400',
    lineHeight: 26,
    marginTop: 8,
  },
  serverInput: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
  },
  button: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 16,
  },
  buttonText: {
    fontSize: 18,
    fontWeight: '600',
  },
});

export default GetStarted;
