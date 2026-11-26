import React from 'react';
import { StyleSheet, Text, View, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

/**
 * Sort control for the Submission list (APP-586): a left label reflecting the active
 * (mode, direction) and three 44px toggle buttons — A-Z (name), calendar (created date),
 * pin (distance). The Distance button is hidden when `showDistance` is false (no location).
 * Presentational — the caller owns `mode`/`dir` and flips direction on re-tap of the active mode.
 */
const LABELS = {
  name: { asc: 'sortNameAsc', desc: 'sortNameDesc' },
  date: { asc: 'sortDateAsc', desc: 'sortDateDesc' },
  distance: { asc: 'sortDistAsc', desc: 'sortDistDesc' },
};

const SortControl = ({ mode = 'date', dir = 'desc', onPick, showDistance = false, trans }) => {
  const theme = useTheme();
  const label = trans[LABELS[mode]?.[dir]] || '';
  const arrow = dir === 'asc' ? 'arrow-up' : 'arrow-down';

  const buttons = [
    { key: 'name', a11y: trans.sortByNameA11y, render: (color) => <AZGlyph color={color} /> },
    { key: 'date', a11y: trans.sortByDateA11y, icon: 'calendar-outline' },
    ...(showDistance
      ? [{ key: 'distance', a11y: trans.sortByDistA11y, icon: 'location-outline' }]
      : []),
  ];

  return (
    <View style={styles.row}>
      <Text style={[styles.label, { color: theme.text.secondary }]} numberOfLines={1}>
        {label}
      </Text>
      <View style={styles.buttons} accessibilityRole="radiogroup">
        {buttons.map((b) => {
          const isActive = mode === b.key;
          const fg = isActive ? '#FFFFFF' : theme.text.secondary;
          return (
            <TouchableOpacity
              key={b.key}
              onPress={() => onPick?.(b.key)}
              accessibilityRole="button"
              accessibilityState={{ selected: isActive }}
              accessibilityLabel={b.a11y}
              testID={`sort-${b.key}`}
              style={[
                styles.button,
                {
                  backgroundColor: isActive ? theme.text.highlight : theme.bg.surfaceElevated1,
                  borderColor: isActive ? theme.text.highlight : theme.border.subtle,
                },
              ]}
            >
              {b.render ? b.render(fg) : <Icon name={b.icon} size={20} color={fg} />}
              {isActive && <Icon name={arrow} size={14} color={fg} />}
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};

const AZGlyph = ({ color }) => (
  <View style={styles.az}>
    <Text style={[styles.azText, { color }]}>A</Text>
    <Text style={[styles.azText, { color }]}>Z</Text>
  </View>
);

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
  },
  label: {
    flex: 1,
    fontSize: 14,
  },
  buttons: {
    flexDirection: 'row',
    gap: 8,
  },
  button: {
    minWidth: 44,
    height: 44,
    paddingHorizontal: 10,
    borderRadius: 22,
    borderWidth: 1.5,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  az: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  azText: {
    fontSize: 11,
    fontWeight: '800',
    lineHeight: 11,
  },
});

export default SortControl;
