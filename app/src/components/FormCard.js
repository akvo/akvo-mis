import React from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../store';
import i18n from '../lib/i18n';
import useTheme from '../lib/theme';

/**
 * Form title, version and the Draft / Pending sync / Synced counts.
 *  - `home`: borderless, meant to sit inside Home's card. Counts render as filled
 *    tiles (APP-585). Counts are PARENT-ONLY; a form with sub-forms shows an
 *    expander (chevron up/down) that lists each sub-form as its own tappable card.
 *  - `monitoring`: a bordered card with a clipboard icon and a chevron (FormOptions).
 *    Keeps the plain coloured counts and the "Submitted" label (a different figure —
 *    all submitted, sync-agnostic — so it must not reuse the home "Pending sync" label).
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
  subFormCount = 0,
  subDraft = 0,
  subPending = 0,
  subSynced = 0,
  expanded = false,
  onToggleExpand = null,
  subForms = [],
  loadingSubForms = false,
}) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const isHome = variant === 'home';
  const sizes = isHome ? homeSizes : monitoringSizes;

  // monitoring keeps the original plain counts; home uses the filled tiles below.
  const stats = [
    { key: 'submitted', label: trans.statSubmitted, value: submitted, color: theme.text.primary },
    { key: 'draft', label: trans.draftText, value: draft, color: theme.status.warning },
    { key: 'synced', label: trans.statSynced, value: synced, color: theme.status.success },
  ];

  const tiles = [
    { key: 'draft', label: trans.draftText, value: draft, token: theme.tile.draft },
    { key: 'submitted', label: trans.statPending, value: submitted, token: theme.tile.pending },
    { key: 'synced', label: trans.statSynced, value: synced, token: theme.tile.synced },
  ];

  const titleText = (
    <Text
      style={[sizes.title, !isHome && styles.flex, { color: theme.text.primary }]}
      numberOfLines={2}
    >
      {title}
    </Text>
  );

  const subFormLabel = `${subFormCount} ${subFormCount > 1 ? trans.subFormsText : trans.subFormText}`;

  // Aggregated monitoring totals, shown on the collapsed header so sub-form status is
  // visible without expanding. Only non-zero states appear.
  const subChips = [
    { key: 'draft', value: subDraft, label: trans.draftText, token: theme.tile.draft },
    { key: 'pending', value: subPending, label: trans.statPending, token: theme.tile.pending },
    { key: 'synced', value: subSynced, label: trans.statSynced, token: theme.tile.synced },
  ].filter((c) => c.value > 0);

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

      {isHome ? (
        <View style={styles.tilesRow}>
          {tiles.map((t) => (
            <View
              key={t.key}
              style={[styles.tile, { backgroundColor: t.token.bg }]}
              testID={`stat-${t.key}`}
            >
              <Text style={[styles.tileCount, { color: t.token.fg }]}>{t.value}</Text>
              <Text style={[styles.tileLabel, { color: t.token.fg }]}>{t.label}</Text>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.statsRow}>
          {stats.map((s) => (
            <View key={s.key} style={styles.stat} testID={`stat-${s.key}`}>
              <Text style={[sizes.count, { color: s.color }]}>{s.value}</Text>
              <Text style={[sizes.statLabel, { color: theme.text.tertiary }]}>{s.label}</Text>
            </View>
          ))}
        </View>
      )}

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

      {isHome && subFormCount > 0 && (
        <>
          <TouchableOpacity
            style={[styles.expandRow, { borderTopColor: theme.border.listDivider }]}
            onPress={onToggleExpand}
            testID="subform-toggle"
            accessibilityRole="button"
          >
            <Text style={[styles.expandText, { color: theme.text.secondary }]}>{subFormLabel}</Text>
            <View style={styles.chipsRow}>
              {subChips.map((c) => (
                <View
                  key={c.key}
                  style={[styles.chip, { backgroundColor: c.token.bg }]}
                  testID={`subsum-${c.key}`}
                >
                  <Text style={[styles.chipText, { color: c.token.fg }]} numberOfLines={1}>
                    {`${c.value} ${c.label}`}
                  </Text>
                </View>
              ))}
            </View>
            <Icon
              name={expanded ? 'chevron-up' : 'chevron-down'}
              size={18}
              color={theme.text.tertiary}
            />
          </TouchableOpacity>
          {expanded &&
            (loadingSubForms ? (
              <ActivityIndicator style={styles.subLoading} color={theme.text.highlight} />
            ) : (
              <View style={styles.subList}>
                {subForms.map((sf) => (
                  <View
                    key={sf.id}
                    style={[
                      styles.subCard,
                      {
                        backgroundColor: theme.bg.surfaceElevated1,
                        borderColor: theme.border.subtle,
                      },
                    ]}
                    testID={`subform-card-${sf.id}`}
                  >
                    <FormCard
                      variant="home"
                      title={sf.name}
                      version={sf.version}
                      submitted={sf.submitted}
                      draft={sf.draft}
                      synced={sf.synced}
                    />
                  </View>
                ))}
              </View>
            ))}
        </>
      )}
    </View>
  );
};

const homeSizes = StyleSheet.create({
  title: { fontSize: 16, fontWeight: '500', lineHeight: 24 },
  version: { fontSize: 12, fontWeight: '500', lineHeight: 16, marginTop: 2 },
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
  tilesRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  tile: {
    flex: 1,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 10,
    gap: 2,
  },
  tileCount: {
    fontSize: 24,
    fontWeight: '700',
    lineHeight: 28,
  },
  tileLabel: {
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 16,
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
  expandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    marginTop: 12,
    paddingTop: 12,
    minHeight: 44,
  },
  expandText: {
    fontSize: 14,
    fontWeight: '600',
  },
  chipsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginLeft: 'auto',
    marginRight: 8,
    flexShrink: 1,
  },
  chip: {
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  subLoading: {
    marginTop: 12,
  },
  subList: {
    marginTop: 8,
    gap: 8,
  },
  subCard: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
});

export default FormCard;
