import React from 'react';
import { View } from 'react-native';
import Titles from './Titles';
import useTheme from '../../lib/theme';

const CenterLayout = ({ children, backgroundColor = null }) => {
  const theme = useTheme();

  return (
    <View
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 16,
        gap: 36,
        backgroundColor: backgroundColor || theme.bg.surfacePrimary,
      }}
      testID="center-layout"
    >
      {children}
    </View>
  );
};

CenterLayout.Titles = Titles;

export default CenterLayout;
