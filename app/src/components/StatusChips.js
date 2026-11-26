import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity } from 'react-native';
import useTheme from '../lib/theme';

/**
 * Status filter chips for the Submission list (APP-586): All / Draft / Pending / Synced with
 * counts. Draft/Pending/Synced use the shared tile tokens; All is neutral. Presentational —
 * the caller owns `active` and `onSelect`. Chips are independent filters (Draft is family-wide),
 * so the counts do not necessarily sum to All.
 */
const StatusChips = ({ counts = {}, active = 'all', onSelect, trans }) => {
  const theme = useTheme();
  const neutral = { bg: theme.bg.surfaceElevated1, fg: theme.text.primary };
  const chips = [
    { key: 'all', label: trans.filterAll, token: neutral },
    { key: 'draft', label: trans.draftText, token: theme.tile.draft },
    { key: 'pending', label: trans.statPending, token: theme.tile.pending },
    { key: 'synced', label: trans.statSynced, token: theme.tile.synced },
  ];
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.scroll}
      contentContainerStyle={styles.row}
      testID="status-chips"
    >
      {chips.map((c) => {
        const isActive = active === c.key;
        return (
          <TouchableOpacity
            key={c.key}
            onPress={() => onSelect?.(c.key)}
            accessibilityRole="button"
            accessibilityState={{ selected: isActive }}
            testID={`chip-${c.key}`}
            style={[
              styles.chip,
              {
                backgroundColor: isActive ? c.token.fg : c.token.bg,
                borderColor: c.token.fg,
              },
            ]}
          >
            <Text
              style={[styles.text, { color: isActive ? c.token.bg : c.token.fg }]}
              numberOfLines={1}
            >
              {`${c.label} ${counts[c.key] || 0}`}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
};

const CHIP_HEIGHT = 44;

const styles = StyleSheet.create({
  // Fixed height + flexGrow:0 so the horizontal scroller doesn't stretch to fill the column
  // (which blew the chips up into full-height bars).
  scroll: {
    flexGrow: 0,
    height: CHIP_HEIGHT + 8,
  },
  row: {
    gap: 8,
    paddingHorizontal: 16,
    alignItems: 'center',
  },
  chip: {
    height: CHIP_HEIGHT,
    paddingHorizontal: 14,
    borderRadius: 22,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default StatusChips;
