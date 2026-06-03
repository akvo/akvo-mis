import React from 'react';
import { Image } from 'react-native';
import appIcon from '../../assets/icon.png';

const LogoImage = () => (
  <Image
    source={appIcon}
    style={{ width: 110, height: 110, borderRadius: 4 }}
    testID="logo-image"
  />
);

export default LogoImage;
