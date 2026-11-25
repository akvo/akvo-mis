import React, { useEffect, useRef, useState } from 'react';
import { View, ScrollView, TouchableOpacity, StyleSheet } from 'react-native';
import { useSQLiteContext } from 'expo-sqlite';
import FormCard from '../FormCard';
import SectionHeader from '../SectionHeader';
import { DatapointSyncState, UserState } from '../../store';
import { crudForms } from '../../database/crud';
import useTheme from '../../lib/theme';

/**
 * Two modes:
 *  - `data` (flat array): Home's form list (APP-585) — each form its own rounded card,
 *    with an optional sub-form expander. One flat list, no sections.
 *  - `sections` ([{ key, title, data }]): the legacy grouped list (collapsible counted
 *    headers over one container). Kept for any other caller.
 * Without either: a plain wrapper for `children`.
 */
const Content = ({
  children = null,
  data = null,
  sections = [],
  action = null,
  footer = null,
}) => {
  const theme = useTheme();
  const db = useSQLiteContext();
  const userId = UserState.useState((s) => s.id);
  const syncingFormId = DatapointSyncState.useState((s) => s.syncingFormId);
  const formProgress = DatapointSyncState.useState((s) => s.formProgress);

  // Expander state lives here, keyed by local form id; sub-form rows cached by backend formId.
  const [expanded, setExpanded] = useState({});
  const [subForms, setSubForms] = useState({});
  const [loadingSub, setLoadingSub] = useState({});
  // Mirror of the cache read inside the effect without making it a dependency (that would loop).
  const subFormsRef = useRef(subForms);
  useEffect(() => {
    subFormsRef.current = subForms;
  }, [subForms]);

  const toggleExpand = (d) => {
    setExpanded((prev) => ({ ...prev, [d.id]: !prev[d.id] }));
  };

  // Fetch sub-form counts for every open parent, and REFETCH them whenever `data` changes
  // (e.g. a new submission refreshes Home), so an expanded card never shows stale counts.
  // The spinner shows only on a first open (nothing cached yet); a `data` refresh updates
  // in the background, keeping the current numbers visible until the new ones land.
  useEffect(() => {
    if (!data) {
      return undefined;
    }
    const open = data.filter((d) => expanded[d?.id]);
    if (!open.length) {
      return undefined;
    }
    let cancelled = false;
    setLoadingSub((prev) => {
      const next = { ...prev };
      open.forEach((d) => {
        if (!subFormsRef.current[d.formId]) {
          next[d.id] = true;
        }
      });
      return next;
    });
    Promise.all(
      open.map(async (d) => ({
        id: d.id,
        formId: d.formId,
        rows: await crudForms.selectSubFormsByParent(db, { parentFormId: d.formId, user: userId }),
      })),
    )
      .then((results) => {
        if (cancelled) {
          return;
        }
        setSubForms((prev) => {
          const next = { ...prev };
          results.forEach((r) => {
            next[r.formId] = r.rows;
          });
          return next;
        });
        setLoadingSub((prev) => {
          const next = { ...prev };
          results.forEach((r) => {
            next[r.id] = false;
          });
          return next;
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [data, expanded, db, userId]);

  const renderCard = (d) => {
    const cardFormId = d?.formId ? Number(d.formId) : null;
    const isSyncing = syncingFormId != null && cardFormId === Number(syncingFormId);
    const progress = cardFormId ? formProgress[cardFormId] : null;
    const syncPercent = progress?.total > 0 ? (progress.processed / progress.total) * 100 : 0;
    const card = (
      <FormCard
        title={d?.registered ? `${d?.name} (${d.registered})` : d?.name}
        version={d?.version}
        submitted={d?.submitted}
        draft={d?.draft}
        synced={d?.synced}
        syncing={isSyncing}
        syncProgress={syncPercent}
        subFormCount={d?.subFormCount || 0}
        subDraft={d?.subDraft || 0}
        subPending={d?.subPending || 0}
        subSynced={d?.subSynced || 0}
        expanded={!!expanded[d?.id]}
        onToggleExpand={() => toggleExpand(d)}
        subForms={subForms[d?.formId] || []}
        loadingSubForms={!!loadingSub[d?.id]}
      />
    );
    return action ? (
      <TouchableOpacity onPress={() => action(d?.id)} testID={`card-touchable-${d?.id}`}>
        {card}
      </TouchableOpacity>
    ) : (
      <View testID={`card-non-touchable-${d?.id}`}>{card}</View>
    );
  };

  // Flat mode (Home).
  if (data) {
    if (!data.length) {
      return <View style={styles.plain}>{children}</View>;
    }
    return (
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {data.map((d) => (
          <View
            key={d?.id}
            style={[styles.flatCard, { backgroundColor: theme.bg.surfaceElevated2 }]}
            testID={`form-card-${d?.id}`}
          >
            {renderCard(d)}
          </View>
        ))}
        {footer && (
          <View style={[styles.flatCard, { backgroundColor: theme.bg.surfaceElevated2 }]}>
            {footer}
          </View>
        )}
      </ScrollView>
    );
  }

  const visible = sections.filter((s) => s.data?.length);
  if (!visible.length) {
    return <View style={styles.plain}>{children}</View>;
  }

  const divider = <View style={[styles.divider, { backgroundColor: theme.border.listDivider }]} />;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      {visible.map((section, sx) => (
        <SectionHeader
          key={section.key}
          title={section.title}
          count={section.data.length}
          testID={`section-header-${section.key}`}
          style={styles.section}
        >
          <View
            style={[styles.container, { backgroundColor: theme.bg.surfaceElevated2 }]}
            testID={`form-group-${section.key}`}
          >
            {section.data.map((d, dx) => (
              <View key={d?.id}>
                {dx > 0 && divider}
                {renderCard(d)}
              </View>
            ))}
            {footer && sx === visible.length - 1 && (
              <>
                {divider}
                {footer}
              </>
            )}
          </View>
        </SectionHeader>
      ))}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  plain: {
    flex: 1,
    width: '100%',
  },
  scroll: {
    width: '100%',
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 16,
  },
  section: {
    marginBottom: 24,
  },
  container: {
    borderRadius: 16,
    padding: 16,
  },
  flatCard: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  divider: {
    height: 1,
    marginVertical: 16,
  },
});

export default Content;
