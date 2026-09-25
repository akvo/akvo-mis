/* eslint-disable react/no-array-index-key */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Card as RneCard, Text } from '@rneui/themed';
import useTheme from '../lib/theme';

const Card = ({ title = null, subTitles = [], syncing = false, syncProgress = 0 }) => {
  const theme = useTheme();
  return (
    <RneCard
      containerStyle={[
        styles.container,
        { backgroundColor: theme.bg.surfaceElevated1 },
        syncing && { borderColor: theme.text.highlight, borderWidth: 1 },
      ]}
    >
      {title && (
        <RneCard.Title style={[styles.title, { color: theme.text.primary }]}>{title}</RneCard.Title>
      )}
      {subTitles?.map((s, sx) => (
        <Text key={sx} style={{ color: theme.text.secondary }}>
          {s}
        </Text>
      ))}
      {syncing && (
        <View
          style={[styles.progressBarContainer, { backgroundColor: theme.border.listDivider }]}
          testID="sync-progress-bar"
        >
          <View
            style={[
              styles.progressBarFill,
              {
                width: `${Math.min(Math.max(syncProgress, 0), 100)}%`,
                backgroundColor: theme.text.highlight,
              },
            ]}
          />
        </View>
      )}
    </RneCard>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    margin: 0,
  },
  title: {
    textAlign: 'left',
    width: '100%',
  },
  progressBarContainer: {
    height: 4,
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 2,
  },
});

export default Card;
