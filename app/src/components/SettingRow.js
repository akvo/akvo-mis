import React from 'react';
import { StyleSheet, Switch, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';
import LevelIcon from './LevelIcon';

/**
 * Figma "Setting Row" (6226:1039). `control` picks the trailing element:
 * `chevron` (default), `value`, `toggle`, `level` (chip with a LevelIcon) or `none`.
 * `level` = { kind, value } for the `level` control.
 */
const SettingRow = ({
  icon = null,
  label,
  description = null,
  control = 'chevron',
  value = null,
  level = null,
  onPress = null,
  onValueChange = null,
  testID = null,
  switchTestID = null,
}) => {
  const theme = useTheme();

  const renderControl = () => {
    if (control === 'chevron') {
      // bottomNav.deselected, not bottomNav.border: that one is near-invisible on dark (APP-481 D-1)
      return <Icon name="chevron-forward" size={20} color={theme.bottomNav.deselected} />;
    }
    if (control === 'value') {
      return (
        <Text
          style={[styles.value, { color: theme.text.secondary }]}
          numberOfLines={1}
          ellipsizeMode="tail"
        >
          {value}
        </Text>
      );
    }
    if (control === 'toggle') {
      return (
        <Switch
          value={!!value}
          onValueChange={onValueChange}
          trackColor={{ true: theme.buttonPrimary.bg, false: theme.border.divider }}
          thumbColor={theme.buttonPrimary.text}
          testID={switchTestID}
        />
      );
    }
    if (control === 'level') {
      return (
        <View style={[styles.chip, { backgroundColor: theme.bg.surfacePrimary }]}>
          <LevelIcon kind={level?.kind} level={level?.value} />
          <Text style={[styles.chipLabel, { color: theme.text.primary }]}>{value}</Text>
        </View>
      );
    }
    return null;
  };

  // Figma fixed heights: 55 with an icon box or a single line, 61 for label + description.
  const minHeight = !icon && description ? 61 : 55;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={!onPress}
      testID={testID}
      style={[styles.row, { minHeight, borderBottomColor: theme.border.divider }]}
      activeOpacity={0.6}
    >
      {icon && (
        <View style={[styles.iconBox, { backgroundColor: theme.input.bg }]}>
          <Icon name={icon} size={20} color={theme.icon.accent} />
        </View>
      )}
      <View style={styles.text}>
        <Text style={[styles.label, { color: theme.text.primary }]}>{label}</Text>
        {description && (
          <Text style={[styles.description, { color: theme.text.tertiary }]}>{description}</Text>
        )}
      </View>
      {renderControl()}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingTop: 8,
    paddingBottom: 10,
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
    gap: 2,
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
    letterSpacing: 0.04,
  },
  value: {
    flexShrink: 1,
    maxWidth: '50%',
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 14,
  },
  chipLabel: {
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 16,
    letterSpacing: 0.04,
  },
});

export default SettingRow;
