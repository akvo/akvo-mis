import buildJson from './build.json';

const defaultBuildParams = {
  ...buildJson,
  serverURL: 'https://mohhs-mis.akvotest.org/api/v1/device',
  apkURL: 'https://mohhs-mis.akvotest.org/app',
};

export default defaultBuildParams;
