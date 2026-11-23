import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

/**
 * Figma "Button Container" (6499:17412): a full-width primary button on a bottom sheet
 * surface. Light and dark come from the theme tokens (APP-481 A25).
 */
const ActionBar = ({ label, onPress, testID = 'action-bar-button' }) => {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.bar,
        {
          backgroundColor: theme.bg.surfaceElevated3,
          borderTopColor: theme.border.listDivider,
          paddingBottom: 20,
        },
      ]}
      testID={`${testID}-bar`}
    >
      <TouchableOpacity
        onPress={onPress}
        testID={testID}
        style={[styles.button, { backgroundColor: theme.buttonPrimary.bg }]}
        activeOpacity={0.8}
        accessibilityRole="button"
      >
        <Text style={[styles.label, { color: theme.buttonPrimary.text }]} numberOfLines={1}>
          {label}
        </Text>
        <Icon name="add" size={24} color={theme.buttonPrimary.text} />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  bar: {
    paddingTop: 12,
    paddingHorizontal: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 16,
  },
  label: {
    fontSize: 16,
    fontWeight: '700',
    lineHeight: 24,
  },
});

export default ActionBar;
