/* eslint-disable react/no-array-index-key */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Text } from '@rneui/themed';
import useTheme from '../../lib/theme';

const Titles = ({ items }) => {
  const theme = useTheme();

  return (
    <View style={styles.heading} testID="center-layout-items">
      {items?.map((item, ix) => (
        <Text key={ix} h4 h4Style={{ color: theme.text.primary }}>
          {item}
        </Text>
      ))}
    </View>
  );
};

const styles = StyleSheet.create({
  heading: { display: 'flex', alignItems: 'center' },
});

export default Titles;
