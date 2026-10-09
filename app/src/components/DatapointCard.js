import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

/**
 * One status per row, by priority: file missing > draft > waiting to sync > synced.
 */
const getStatus = (item) => {
  if (item.needsRetake) {
    return 'missing';
  }
  if (item.submitted === 0) {
    return 'draft';
  }
  return item.isSynced ? 'synced' : 'pending';
};

const STATUS_ICONS = {
  missing: { name: 'alert-circle', color: (t) => t.status.error, label: 'photoMissingText' },
  draft: { name: 'pencil', color: (t) => t.status.draft, label: 'draftText' },
  pending: { name: 'time', color: (t) => t.status.warning, label: 'legendPending' },
  synced: { name: 'checkmark-circle', color: (t) => t.status.success, label: 'legendSynced' },
};

/** Name, one meta line and a status icon. Row touch/swipe stays with the caller. */
const DatapointCard = ({ item, meta, trans }) => {
  const theme = useTheme();
  const status = getStatus(item);
  const icon = STATUS_ICONS[status];
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: theme.bg.surfaceElevated2, borderColor: theme.border.subtle },
      ]}
    >
      <View style={styles.text}>
        <Text style={[styles.name, { color: theme.text.primary }]} numberOfLines={1}>
          {item.name}
        </Text>
        <Text style={[styles.meta, { color: theme.text.tertiary }]} numberOfLines={1}>
          {meta}
        </Text>
      </View>
      <Icon
        name={icon.name}
        size={20}
        color={icon.color(theme)}
        testID={`status-${status}-${item.id}`}
        accessibilityLabel={trans[icon.label]}
      />
    </View>
  );
};

/** Explains every status icon `items` shows, in STATUS_ICONS order (A24). */
const DatapointLegend = ({ trans, items = [] }) => {
  const theme = useTheme();
  const shown = new Set(items.map(getStatus));
  return (
    <View style={styles.legend} testID="status-legend">
      {Object.keys(STATUS_ICONS)
        .filter((status) => shown.has(status))
        .map((status) => (
          <View key={status} style={styles.legendRow}>
            <Icon
              name={STATUS_ICONS[status].name}
              size={16}
              color={STATUS_ICONS[status].color(theme)}
            />
            <Text style={[styles.legendText, { color: theme.text.tertiary }]}>
              {trans[STATUS_ICONS[status].label]}
            </Text>
          </View>
        ))}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 64,
    paddingHorizontal: 16,
    paddingVertical: 11,
    borderWidth: 1,
    borderRadius: 12,
  },
  text: {
    flex: 1,
    gap: 2,
  },
  name: {
    fontSize: 16,
    fontWeight: '500',
    lineHeight: 24,
  },
  meta: {
    fontSize: 12,
    fontWeight: '400',
    lineHeight: 16,
  },
  legend: {
    gap: 4,
    paddingTop: 8,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  legendText: {
    fontSize: 12,
    fontWeight: '300',
    lineHeight: 16,
  },
});

export { getStatus, DatapointLegend };
export default DatapointCard;
