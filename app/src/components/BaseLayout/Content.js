import React from 'react';
import { View, ScrollView, TouchableOpacity, StyleSheet } from 'react-native';
import FormCard from '../FormCard';
import SectionHeader from '../SectionHeader';
import { DatapointSyncState } from '../../store';
import useTheme from '../../lib/theme';

/**
 * With `sections` ([{ key, title, data }]): Home's form lists — each a collapsible, counted
 * title over one container, forms split by dividers. Sections without data are left out,
 * and `footer` closes whichever one comes last. Without any: a plain wrapper for `children`.
 */
const Content = ({ children = null, sections = [], action = null, footer = null }) => {
  const theme = useTheme();
  const syncingFormId = DatapointSyncState.useState((s) => s.syncingFormId);
  const formProgress = DatapointSyncState.useState((s) => s.formProgress);

  const visible = sections.filter((s) => s.data?.length);
  if (!visible.length) {
    return <View style={styles.plain}>{children}</View>;
  }

  const divider = <View style={[styles.divider, { backgroundColor: theme.border.listDivider }]} />;

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
  divider: {
    height: 1,
    marginVertical: 16,
  },
});

export default Content;
