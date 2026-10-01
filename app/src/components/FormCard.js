import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../store';
import i18n from '../lib/i18n';
import useTheme from '../lib/theme';

/**
 * Form title, version and the Submitted / Draft / Synced counts.
 *  - `home`: borderless, meant to sit inside Home's grouped container.
 *  - `monitoring`: a bordered card with a clipboard icon and a chevron (FormOptions).
 * Count colors are shared by both variants (D-2): green only ever means "on the server".
 */
const FormCard = ({
  variant = 'home',
  title,
  version,
  submitted = 0,
  draft = 0,
  synced = 0,
  syncing = false,
  syncProgress = 0,
}) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const isHome = variant === 'home';
  const sizes = isHome ? homeSizes : monitoringSizes;

  const stats = [
    { key: 'submitted', label: trans.statSubmitted, value: submitted, color: theme.text.primary },
    { key: 'draft', label: trans.draftText, value: draft, color: theme.status.warning },
    { key: 'synced', label: trans.statSynced, value: synced, color: theme.status.success },
  ];

  const titleText = (
    <Text
      style={[sizes.title, !isHome && styles.flex, { color: theme.text.primary }]}
      numberOfLines={2}
    >
      {title}
    </Text>
  );

  return (
    <View
      style={
        isHome
          ? null
          : [
              styles.monitoringCard,
              { backgroundColor: theme.bg.surfaceElevated1, borderColor: theme.border.subtle },
            ]
      }
    >
      {isHome ? (
        titleText
      ) : (
        <View style={styles.headRow}>
          <Icon name="clipboard-outline" size={20} color={theme.status.success} />
          {titleText}
          <Icon name="chevron-forward" size={20} color={theme.text.tertiary} />
        </View>
      )}
      <Text style={[sizes.version, { color: isHome ? theme.text.highlight : theme.text.tertiary }]}>
        {`${trans.versionLabel}${version}`}
      </Text>
      <View style={[styles.statsRow, { marginTop: isHome ? 12 : 0 }]}>
        {stats.map((s) => (
          <View key={s.key} style={styles.stat} testID={`stat-${s.key}`}>
            <Text style={[sizes.count, { color: s.color }]}>{s.value}</Text>
            <Text style={[sizes.statLabel, { color: theme.text.tertiary }]}>{s.label}</Text>
          </View>
        ))}
      </View>
      {syncing && (
        <View
          style={[styles.progressTrack, { backgroundColor: theme.border.listDivider }]}
          testID="sync-progress-bar"
        >
          <View
            style={[
              styles.progressFill,
              {
                width: `${Math.min(Math.max(syncProgress, 0), 100)}%`,
                backgroundColor: theme.text.highlight,
              },
            ]}
          />
        </View>
      )}
    </View>
  );
};

const homeSizes = StyleSheet.create({
  title: { fontSize: 16, fontWeight: '500', lineHeight: 24 },
  version: { fontSize: 12, fontWeight: '500', lineHeight: 16, marginTop: 2 },
  count: { fontSize: 12, fontWeight: '500', lineHeight: 16 },
  statLabel: { fontSize: 12, fontWeight: '400', lineHeight: 16 },
});

const monitoringSizes = StyleSheet.create({
  title: { fontSize: 16, fontWeight: '700', lineHeight: 24 },
  version: { fontSize: 12, fontWeight: '400', lineHeight: 16 },
  count: { fontSize: 16, fontWeight: '700', lineHeight: 24 },
  statLabel: { fontSize: 11, fontWeight: '400', lineHeight: 16 },
});

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  monitoringCard: {
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 10,
  },
  headRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 20,
  },
  stat: {
    gap: 1,
  },
  progressTrack: {
    height: 4,
    borderRadius: 2,
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
});

export default FormCard;
