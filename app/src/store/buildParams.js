import { Store } from 'pullstate';
import defaultBuildParams from '../build';

const BuildParamsState = new Store({
  apkName: defaultBuildParams?.apkName,
  authenticationType: defaultBuildParams?.authenticationType || [
    'code_assignment',
    'username',
    'password',
  ],
  serverURL: defaultBuildParams?.serverURL,
  apkURL: defaultBuildParams?.apkURL,
  debugMode: defaultBuildParams?.debugMode || false,
  dataSyncInterval: defaultBuildParams?.dataSyncInterval || 3600,
  errorHandling: defaultBuildParams?.errorHandling || true,
  loggingLevel: defaultBuildParams?.loggingLevel || 'verbose',
  appVersion: defaultBuildParams?.appVersion || '1.0.0',
  gpsThreshold: defaultBuildParams?.gpsThreshold || 20, // meters
  gpsInterval: 60, // seconds
  gpsAccuracyLevel: 4, // High
  geoLocationTimeout: 60, // seconds
  imageQuality: 'low', // Image compression quality preset
  // Mirror camera captures into the device gallery so a photo the app loses can
  // still be recovered. Off by default: it needs a media permission and puts
  // site photos where any app can read them.
  saveToGallery: 0,
  // Polygon validation severity switches. ON (1) means a failed rule BLOCKS submission; OFF
  // means it warns instead. The rule always runs either way - there is no value here that
  // skips a check. Default strict; GEO-002 D-4.
  validatePolygonShape: 1,
  validatePolygonArea: 1,
});

export default BuildParamsState;
