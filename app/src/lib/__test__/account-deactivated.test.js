import * as BackgroundTask from 'expo-background-task';
import { handleAccountDeactivated } from '../background-task';
import notification from '../notification';
import {
  ACCOUNT_DEACTIVATED_NOTIFICATION,
  SYNC_FORM_SUBMISSION_TASK_NAME,
  SYNC_FORM_VERSION_TASK_NAME,
} from '../constants';

jest.mock('expo-task-manager', () => ({
  defineTask: jest.fn(),
  isTaskRegisteredAsync: jest.fn(() => Promise.resolve(false)),
  getRegisteredTasksAsync: jest.fn(() => Promise.resolve([])),
}));
jest.mock('expo-background-task', () => ({
  unregisterTaskAsync: jest.fn(() => Promise.resolve()),
  registerTaskAsync: jest.fn(() => Promise.resolve()),
  getStatusAsync: jest.fn(() => Promise.resolve()),
  BackgroundTaskResult: { Success: 1, Failed: 2 },
}));
jest.mock('../notification', () => ({
  __esModule: true,
  default: { sendPushNotification: jest.fn(() => Promise.resolve()) },
}));

/**
 * The server already refuses these calls -- IsMobileAssignment checks
 * both is_active and deleted_at. What was missing was any sign of it on
 * the device: every sync path caught the 403, logged it to Sentry and
 * rescheduled, so the app quietly stopped working and kept polling.
 */
describe('a device whose person has been deactivated', () => {
  it('names the cause, and stops polling an endpoint that keeps refusing', async () => {
    await handleAccountDeactivated();

    expect(notification.sendPushNotification).toHaveBeenCalledWith(
      ACCOUNT_DEACTIVATED_NOTIFICATION,
    );
    expect(BackgroundTask.unregisterTaskAsync).toHaveBeenCalledWith(
      SYNC_FORM_VERSION_TASK_NAME,
    );
    expect(BackgroundTask.unregisterTaskAsync).toHaveBeenCalledWith(
      SYNC_FORM_SUBMISSION_TASK_NAME,
    );
  });

  it('tells them once, not on every background interval', async () => {
    // The task runs at least every 15 minutes. Repeating a message
    // only an administrator can act on is noise, not information.
    notification.sendPushNotification.mockClear();

    await handleAccountDeactivated();

    expect(notification.sendPushNotification).not.toHaveBeenCalled();
  });
});
