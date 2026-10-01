import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Image as RneImage } from '@rneui/themed';
import useTheme from '../lib/theme';

const Image = ({ src = '', style = {} }) => {
  const theme = useTheme();
  return src ? (
    <RneImage
      source={{ uri: src }}
      containerStyle={{ ...styles.image, backgroundColor: theme.bg.surfaceTertiary, ...style }}
      testID="image-component"
    />
  ) : (
    <View style={[styles.image, { backgroundColor: theme.bg.surfaceTertiary }]} testID="image-skeleton" />
  );
};

const styles = StyleSheet.create({
  image: { width: 110, height: 110, borderRadius: 4 },
});

export default Image;
