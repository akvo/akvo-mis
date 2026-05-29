import buildJson from './build.json';

const defaultBuildParams = {
  ...buildJson,
  serverURL: 'http://localhost:3000/api/v1/device', // Mobile device: replace localhost with IP_ADDRESS from .env
  apkURL: '',
};

export default defaultBuildParams;
