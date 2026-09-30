import React, { useEffect } from 'react';
import { NavigationContainer, useNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { BackHandler } from 'react-native';
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
  OverlapMapViewPage,
  UsersPage,
  FormDataDetailsPage,
  AddNewForm,
  AboutPage,
  SubmissionPage,
  FormOptionsPage,
} from '../pages';
import { UIState, AuthState, FormState } from '../store';
import { backgroundTask, notification } from '../lib';
import { SYNC_FORM_SUBMISSION_TASK_NAME, SYNC_FORM_VERSION_TASK_NAME } from '../lib/constants';

export const reactNavigationIntegration = Sentry.reactNavigationIntegration();

const Stack = createNativeStackNavigator();

const RootNavigator = () => {
  const currentPage = UIState.useState((s) => s.currentPage);
  const token = AuthState.useState((s) => s.token); // user already has session
  const db = useSQLiteContext();

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!token || !['Home', 'AddUser'].includes(currentPage)) {
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
          <Stack.Screen name="Home" component={HomePage} />
          <Stack.Screen name="Settings" component={SettingsPage} />
          <Stack.Screen name="About" component={AboutPage} />
          <Stack.Screen name="SettingsForm" component={SettingsFormPage} />
          <Stack.Screen name="FormPage" component={FormPage} />
          <Stack.Screen name="MapView" component={MapViewPage} />
          <Stack.Screen name="MapDrawView" component={MapDrawViewPage} />
          <Stack.Screen name="OverlapMapView" component={OverlapMapViewPage} />
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
    // listen to route change
    const currentRoute = state.routes[state.routes.length - 1].name;
    if (['Home'].includes(currentRoute)) {
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
