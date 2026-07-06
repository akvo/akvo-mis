import buildJson from './build.json';

const defaultBuildParams = {
  ...buildJson,
  serverURL: '', // Configure: https://<your-domain>/api/v1/device
  apkURL: '', // Configure: https://<your-domain>/app
};

export default defaultBuildParams;
