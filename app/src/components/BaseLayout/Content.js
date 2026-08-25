import React from 'react';
import { View, ScrollView, TouchableOpacity } from 'react-native';
import Card from '../Card';
import Stack from '../Stack';
import { DatapointSyncState } from '../../store';

const Content = ({ children = null, data = [], columns = 1, action = null }) => {
  const syncingFormId = DatapointSyncState.useState((s) => s.syncingFormId);
  const formProgress = DatapointSyncState.useState((s) => s.formProgress);

  if (data?.length) {
    return (
      <ScrollView
        style={{ width: '100%' }}
        // paddingBottom clears the floating action button, which overlays this list
        contentContainerStyle={{
          flexGrow: 1,
          paddingHorizontal: 8,
          paddingTop: 8,
          paddingBottom: 88,
        }}
      >
        <Stack row columns={columns}>
          {data?.map((d) => {
            const cardFormId = d?.formId ? Number(d.formId) : null;
            const isSyncing = syncingFormId != null && cardFormId === Number(syncingFormId);
            const progress = cardFormId ? formProgress[cardFormId] : null;
            const hasProgress = progress?.total > 0;
            const syncPercent = hasProgress ? (progress.processed / progress.total) * 100 : 0;

            return action ? (
              <TouchableOpacity
                key={d?.id}
                type="clear"
                onPress={() => action(d?.id)}
                testID={`card-touchable-${d?.id}`}
                style={{ width: '100%' }}
              >
                <Card
                  title={`${d?.name} ${d?.registered ? `(${d.registered})` : ''}`}
                  subTitles={d?.subtitles}
                  syncing={isSyncing}
                  syncProgress={syncPercent}
                />
              </TouchableOpacity>
            ) : (
              <View key={d?.id} testID={`card-non-touchable-${d?.id}`} style={{ width: '100%' }}>
                <Card
                  title={`${d?.name} ${d?.registered ? `(${d.registered})` : ''}`}
                  subTitles={d?.subtitles}
                  syncing={isSyncing}
                  syncProgress={syncPercent}
                />
              </View>
            );
          })}
        </Stack>
      </ScrollView>
    );
  }
  return <View style={{ flex: 1, width: '100%' }}>{children}</View>;
};

export default Content;
