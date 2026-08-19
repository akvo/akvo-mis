/* eslint-disable import/prefer-default-export */

export const SYNC_FORM_VERSION_TASK_NAME = 'sync-form-version';

export const SYNC_FORM_SUBMISSION_TASK_NAME = 'sync-form-submission';

export const SYNC_STATUS = {
  on_progress: 1,
  re_sync: 2,
  success: 3,
  failed: 4,
};

export const SUBMISSION_TYPES = {
  registration: 1,
  monitoring: 2,
};

export const DATABASE_NAME = 'app.db';

export const DATABASE_VERSION = 9;

// How long the automatic update dialog stays suppressed after "Later".
export const SKIP_UPDATE_DURATION_MS = 24 * 60 * 60 * 1000;

export const QUESTION_TYPES = {
  text: 'text',
  number: 'number',
  date: 'date',
  image: 'image',
  geo: 'geo',
  option: 'option',
  multiple_option: 'multiple_option',
  cascade: 'cascade',
  autofield: 'autofield',
  attachment: 'attachment',
  signature: 'signature',
};

export const jobStatus = {
  PENDING: 1,
  ON_PROGRESS: 2,
  SUCCESS: 3,
  FAILED: 4,
};

export const MAX_ATTEMPT = 3;

export const SYNC_DATAPOINT_JOB_NAME = 'sync-form-datapoints';

export const SYNC_DATAPOINT_BACKGROUND_TASK_NAME = 'sync-datapoint-background';
