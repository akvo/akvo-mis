import React from 'react';
import { StyleSheet, Text } from 'react-native';
import useTheme from '../lib/theme';

// Uppercased by style, not by the string, so the i18n text stays as written.
const SectionLabel = ({ children, style = null, testID = null }) => {
  const theme = useTheme();
  return (
    <Text style={[styles.label, { color: theme.text.tertiary }, style]} testID={testID}>
      {children}
    </Text>
  );
};

const styles = StyleSheet.create({
  label: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});

export default SectionLabel;
