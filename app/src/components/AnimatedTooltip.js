import React from 'react';
import { View, StyleSheet } from 'react-native';
import RenderHtml from 'react-native-render-html';
import useTheme from '../lib/theme';

const AnimatedTooltip = ({ visible = false, content = null }) => {
  const theme = useTheme();

  if (!visible) {
    return null;
  }

  return (
    <View style={{ paddingHorizontal: 10 }}>
      <View style={[styles.arrow, { borderBottomColor: theme.bg.surfaceElevated3 }]} />
      <View style={[styles.tooltipContainer, { backgroundColor: theme.bg.surfaceElevated3 }]}>
        <RenderHtml
          source={{ html: content }}
          contentWidth={100}
          baseStyle={{ color: theme.text.primary }}
        />
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  arrow: {
    width: 0,
    height: 0,
    backgroundColor: 'transparent',
    borderStyle: 'solid',
    borderLeftWidth: 8,
    borderRightWidth: 8,
    borderBottomWidth: 10,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    marginLeft: 0,
  },
  tooltipContainer: {
    padding: 10,
    marginLeft: -10,
    maxWidth: 360,
    borderRadius: 5,
    shadowOpacity: 0.3,
    marginTop: -1,
  },
});

export default AnimatedTooltip;
