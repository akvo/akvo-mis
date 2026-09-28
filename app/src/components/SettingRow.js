import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

const SettingRow = ({ icon, label, description = null, onPress, testID = null }) => {
  const theme = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      testID={testID}
      style={[styles.row, { borderBottomColor: theme.border.divider }]}
      activeOpacity={0.6}
    >
      <View style={[styles.iconBox, { backgroundColor: theme.input.bg }]}>
        <Icon name={icon} size={20} color={theme.icon.accent} />
      </View>
      <View style={styles.text}>
        <Text style={[styles.label, { color: theme.text.primary }]}>{label}</Text>
        {description && (
          <Text style={[styles.description, { color: theme.text.tertiary }]}>{description}</Text>
        )}
      </View>
      {/* bottomNav.deselected, not bottomNav.border: that one is near-invisible on dark (D-1) */}
      <Icon name="chevron-forward" size={20} color={theme.bottomNav.deselected} />
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    flex: 1,
  },
  label: {
    fontSize: 16,
    fontWeight: '500',
    lineHeight: 24,
  },
  description: {
    fontSize: 12,
    fontWeight: '400',
    lineHeight: 16,
  },
});

export default SettingRow;
