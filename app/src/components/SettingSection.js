import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import useTheme from '../lib/theme';

// A titled block of SettingRows, as the Figma Settings frames lay them out (APP-487).
const SettingSection = ({ title = null, children, testID = null }) => {
  const theme = useTheme();
  return (
    <View style={styles.section} testID={testID}>
      {title && <Text style={[styles.title, { color: theme.topNav.text }]}>{title}</Text>}
      <View style={styles.rows}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  section: {
    paddingBottom: 8,
  },
  title: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 18,
    fontWeight: '500',
    lineHeight: 26,
    letterSpacing: -0.04,
  },
  rows: {
    paddingHorizontal: 16,
  },
});

export default SettingSection;
