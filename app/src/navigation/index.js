import React, { useEffect } from 'react';
import { BackHandler, ToastAndroid, View } from 'react-native';
import { NavigationContainer, useNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import * as Sentry from '@sentry/react-native';
import { useSQLiteContext } from 'expo-sqlite';

import {
  HomePage,
  GetStartedPage,
  AuthFormPage,
  AuthByPassFormPage,
  SettingsPage,
  SettingsFormPage,
  FormPage,
  AddUserPage,
  MapViewPage,
  MapDrawViewPage,
  UsersPage,
  FormDataDetailsPage,
  AddNewForm,
  AboutPage,
  SubmissionPage,
  FormOptionsPage,
} from '../pages';
import { UIState, AuthState, FormState, DatapointSyncState } from '../store';
import { backgroundTask, notification, i18n } from '../lib';
import useTheme from '../lib/theme';
import {
  SYNC_STATUS,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
} from '../lib/constants';

export const reactNavigationIntegration = Sentry.reactNavigationIntegration();

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

// Placeholder component for the Sync tab (never rendered, tab press is intercepted)
const SyncPlaceholder = () => <View />;

const TAB_ICON_SIZE = 22;

const HomeTabIcon = ({ color }) => <Icon name="home-outline" size={TAB_ICON_SIZE} color={color} />;
const SettingsTabIcon = ({ color }) => (
  <Icon name="settings-outline" size={TAB_ICON_SIZE} color={color} />
);
const SyncTabIcon = () => {
  const theme = useTheme();
  const syncInProgress = DatapointSyncState.useState((s) => s.inProgress);
  return (
    <Icon
      name="refresh-outline"
      size={TAB_ICON_SIZE}
      color={syncInProgress ? theme.status.success : theme.bottomNav.deselected}
    />
  );
};

const HomeTabs = () => {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const activeLang = UIState.useState((s) => s.lang);
  const isOnline = UIState.useState((s) => s.online);
  const syncInProgress = DatapointSyncState.useState((s) => s.inProgress);
  const trans = i18n.text(activeLang);

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: theme.bottomNav.bg,
          borderTopColor: theme.bottomNav.border,
          borderTopWidth: 1,
          paddingTop: 10,
          paddingBottom: Math.max(insets.bottom, 10),
          height: 70 + Math.max(insets.bottom, 10),
        },
        tabBarActiveTintColor: theme.bottomNav.selected,
        tabBarInactiveTintColor: theme.bottomNav.deselected,
        tabBarItemStyle: {
          borderRadius: 16,
          marginHorizontal: 8,
          paddingVertical: 4,
        },
        tabBarActiveBackgroundColor: theme.bg.surfaceTranslucent,
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '700',
          marginTop: 4,
        },
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomePage}
        options={{
          tabBarLabel: trans.homePageTitle,
          tabBarIcon: HomeTabIcon,
          tabBarTestID: 'tab-home',
        }}
      />
      <Tab.Screen
        name="SettingsTab"
        component={SettingsPage}
        options={{
          tabBarLabel: trans.settingsPageTitle,
          tabBarIcon: SettingsTabIcon,
          tabBarTestID: 'tab-settings',
        }}
      />
      <Tab.Screen
        name="SyncTab"
        component={SyncPlaceholder}
        options={{
          tabBarLabel: syncInProgress ? trans.syncingText : trans.syncDataPointBtn,
          tabBarIcon: SyncTabIcon,
          tabBarLabelStyle: {
            fontSize: 12,
            fontWeight: '700',
            marginTop: 4,
            color: syncInProgress ? theme.status.success : theme.bottomNav.deselected,
          },
          tabBarTestID: 'tab-sync',
        }}
        listeners={({ navigation }) => ({
          tabPress: (e) => {
            e.preventDefault();
            if (!isOnline) {
              ToastAndroid.show(trans.offlineText, ToastAndroid.SHORT);
              return;
            }
            if (syncInProgress) {
              ToastAndroid.show(trans.syncingText, ToastAndroid.SHORT);
              return;
            }
            UIState.update((s) => {
              s.statusBar = {
                type: SYNC_STATUS.on_progress,
                bgColor: '#1651b6',
                icon: 'sync',
              };
              s.triggerSync = true;
            });
            navigation.navigate('HomeTab');
          },
        })}
      />
    </Tab.Navigator>
  );
};

const RootNavigator = () => {
  const currentPage = UIState.useState((s) => s.currentPage);
  const token = AuthState.useState((s) => s.token); // user already has session
  const db = useSQLiteContext();

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!token || !['Home', 'HomeTab', 'AddUser'].includes(currentPage)) {
        // Allow navigation if user is not logged in
        return false;
      }
      // Prevent navigation if user is logged in
      return true;
    });
    return () => backHandler.remove();
  }, [token, currentPage]);

  useEffect(() => {
    notification.registerForPushNotificationsAsync();
    const responseListener = Notifications.addNotificationResponseReceivedListener((res) => {
      const notificationBody = res?.notification?.request;
      const notificationType = notificationBody?.content?.data?.notificationType;
      if (notificationType === 'sync-form-version') {
        backgroundTask.syncFormVersion(db, { showNotificationOnly: false });
      }
    });
    return () => {
      responseListener.remove();
    };
  }, [db]);

  useEffect(() => {
    backgroundTask.backgroundTaskStatus(SYNC_FORM_VERSION_TASK_NAME);
    backgroundTask.backgroundTaskStatus(SYNC_FORM_SUBMISSION_TASK_NAME);
  }, []);

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }} initialRouteName={currentPage}>
      {!token ? (
        <>
          <Stack.Screen name="GetStarted" component={GetStartedPage} />
          <Stack.Screen name="AuthForm" component={AuthFormPage} />
          <Stack.Screen name="AuthByPassForm" component={AuthByPassFormPage} />
        </>
      ) : (
        <>
          <Stack.Screen name="Home" component={HomeTabs} />
          <Stack.Screen name="About" component={AboutPage} />
          <Stack.Screen name="SettingsForm" component={SettingsFormPage} />
          <Stack.Screen name="FormPage" component={FormPage} />
          <Stack.Screen name="MapView" component={MapViewPage} />
          <Stack.Screen name="MapDrawView" component={MapDrawViewPage} />
          <Stack.Screen name="AddUser" component={AddUserPage} />
          <Stack.Screen name="Users" component={UsersPage} />
          <Stack.Screen name="FormDataDetails" component={FormDataDetailsPage} />
          <Stack.Screen name="AddNewForm" component={AddNewForm} />
          <Stack.Screen name="Submission" component={SubmissionPage} />
          <Stack.Screen name="FormOptions" component={FormOptionsPage} />
        </>
      )}
    </Stack.Navigator>
  );
};

const Navigation = () => {
  const navigationRef = useNavigationContainerRef();

  const handleOnChangeNavigation = (state) => {
    if (!state) {
      return;
    }
    // listen to route change — resolve nested tab navigators
    const topRoute = state.routes[state.routes.length - 1];
    const currentRoute = topRoute?.state
      ? topRoute.state.routes[topRoute.state.index]?.name
      : topRoute.name;
    if (['Home', 'HomeTab'].includes(currentRoute)) {
      // reset form values
      FormState.update((s) => {
        s.currentValues = {};
        s.visitedQuestionGroup = [];
        s.surveyDuration = 0;
      });
    }
    UIState.update((s) => {
      s.currentPage = currentRoute;
    });
  };

  return (
    <NavigationContainer
      ref={navigationRef}
      onStateChange={handleOnChangeNavigation}
      testID="navigation-element"
      onReady={() => {
        reactNavigationIntegration.registerNavigationContainer(navigationRef);
      }}
    >
      <RootNavigator />
    </NavigationContainer>
  );
};

export default Navigation;
