import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import useTheme from '../lib/theme';

/**
 * Figma "Button Container" (6499:17412): a full-width primary button on a bottom sheet
 * surface. Light and dark come from the theme tokens (APP-481 A25).
 */
const ActionBar = ({ label, onPress, testID = 'action-bar-button' }) => {
  const theme = useTheme();
  // Absolutely positioned elements anchor to the screen edge, below the Android
  // navigation bar, so the inset is added here; the bar's surface runs under it.
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.bar,
        { backgroundColor: theme.bg.surfaceElevated3, paddingBottom: 24 + insets.bottom },
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
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingTop: 16,
    paddingHorizontal: 16,
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
