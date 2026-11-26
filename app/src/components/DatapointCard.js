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
  if (!item.isSynced) {
    return 'pending';
  }
  // Only the user's own uploads get the green check. Registrations downloaded from the server
  // (locallyCreated 0) are master data — no badge (APP-586).
  return item.locallyCreated === 1 ? 'synced' : 'master';
};

/**
 * Badge colors reuse the APP-585 tile tokens: the solid badge fill is the tile's `fg`, the glyph
 * is the tile's `bg` — the pairing already clears 4.5:1 in both themes. `missing` is the one
 * status without a tile, so it uses the error color with a white glyph.
 */
const BADGE = {
  missing: { icon: 'alert', fill: (t) => t.status.error, glyph: () => '#FFFFFF', label: 'photoMissingText' },
  draft: { icon: 'pencil', fill: (t) => t.tile.draft.fg, glyph: (t) => t.tile.draft.bg, label: 'draftText' },
  pending: { icon: 'time', fill: (t) => t.tile.pending.fg, glyph: (t) => t.tile.pending.bg, label: 'legendPending' },
  synced: { icon: 'checkmark', fill: (t) => t.tile.synced.fg, glyph: (t) => t.tile.synced.bg, label: 'legendSynced' },
};

/** Name, one meta line, an optional distance line, and a circular status badge. */
const DatapointCard = ({ item, meta, distance = null, trans }) => {
  const theme = useTheme();
  const status = getStatus(item);
  const badge = BADGE[status];
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
        {distance ? (
          <View style={styles.distanceRow}>
            <Icon name="location" size={13} color={theme.text.highlight} />
            <Text style={[styles.distance, { color: theme.text.highlight }]} numberOfLines={1}>
              {distance}
            </Text>
          </View>
        ) : null}
      </View>
      {badge ? (
        <View
          style={[styles.badge, { backgroundColor: badge.fill(theme) }]}
          testID={`status-${status}-${item.id}`}
          accessibilityRole="image"
          accessibilityLabel={trans[badge.label]}
        >
          <Icon name={badge.icon} size={18} color={badge.glyph(theme)} />
        </View>
      ) : null}
    </View>
  );
};

/** Explains every status badge `items` show, in BADGE order (A24). */
const DatapointLegend = ({ trans, items = [] }) => {
  const theme = useTheme();
  const shown = new Set(items.map(getStatus));
  return (
    <View style={styles.legend} testID="status-legend">
      {Object.keys(BADGE)
        .filter((status) => shown.has(status))
        .map((status) => (
          <View key={status} style={styles.legendRow}>
            <Icon name={BADGE[status].icon} size={16} color={BADGE[status].fill(theme)} />
            <Text style={[styles.legendText, { color: theme.text.tertiary }]}>
              {trans[BADGE[status].label]}
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
  distanceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  distance: {
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 16,
  },
  badge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
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
