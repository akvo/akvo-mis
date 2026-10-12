/* eslint-disable no-console */
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Alert, Platform } from 'react-native';
import { ACCOUNT_DEACTIVATED_NOTIFICATION, SYNC_FORM_SUBMISSION_TASK_NAME } from './constants';

const registerForPushNotificationsAsync = async () => {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    });
  }
  if (Device.isDevice) {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== 'granted') {
      // Show alert
      Alert.alert(
        'Push Notification Permission',
        'Please enable push notification permissions in your device settings to receive updates about form synchronization.',
        [{ text: 'OK' }],
      );
      return;
    }
    await Notifications.getExpoPushTokenAsync().data;
  }
};

const sendPushNotification = async (type = 'sync-form-version') => {
  const data = {
    notificationType: type,
  };
  let notificationBody = null;
  switch (type) {
    case ACCOUNT_DEACTIVATED_NOTIFICATION:
      notificationBody = {
        content: {
          title: 'Account deactivated',
          body: 'Your account has been deactivated. Contact your administrator.',
          data,
        },
        trigger: null,
      };
      break;
    case SYNC_FORM_SUBMISSION_TASK_NAME:
      notificationBody = {
        content: {
          title: 'Sync submission completed',
          body: 'Your submission has been successfully synchronized.',
          data,
        },
        trigger: null,
      };
      break;
    default:
      notificationBody = {
        content: {
          title: 'New Form version available',
          body: 'A new version of the form is now available',
          data,
        },
        trigger: null,
      };
      break;
  }
  await Notifications.scheduleNotificationAsync(notificationBody);
};

const notificationHandler = () => ({
  registerForPushNotificationsAsync,
  sendPushNotification,
});

const notification = notificationHandler();
export default notification;
