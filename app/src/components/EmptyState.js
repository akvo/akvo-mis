import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import useTheme from '../lib/theme';
import paperLight from '../../assets/empty-state/paper-light.png';
import paperDark from '../../assets/empty-state/paper-dark.png';
import arrowLight from '../../assets/empty-state/arrow-light.png';
import arrowDark from '../../assets/empty-state/arrow-dark.png';

/**
 * Figma "Form — empty state" (6499:17376 light, 6218:1095 dark): illustration, title, body
 * and a hand-drawn arrow. The artwork is Figma's SVG rasterised per theme — the app has no
 * SVG renderer (APP-481 A23).
 *
 * The arrow box sits centred under the text, then shifts sideways. `right` is Figma's own
 * position, tip over the right half of a full-width bottom button; `centre` puts the tip on
 * the screen's centre line, over the middle tab (Home's Settings) — the tip is 67px right
 * of the box centre (A23, A25).
 */
const ARROW_SHIFT = { right: 50, centre: -67 };

const EmptyState = ({
  title,
  body,
  showArrow = true,
  arrowTip = 'right',
  style = null,
  testID = 'empty-state',
}) => {
  const theme = useTheme();
  return (
    <View style={[styles.container, style]} testID={testID}>
      <Image source={theme.isDark ? paperDark : paperLight} style={styles.paper} />
      <View style={styles.text}>
        <Text style={[styles.title, { color: theme.text.primary }]}>{title}</Text>
        <Text style={[styles.body, { color: theme.text.secondary }]}>{body}</Text>
      </View>
      {showArrow && (
        <View
          style={[styles.arrowBox, { transform: [{ translateX: ARROW_SHIFT[arrowTip] }] }]}
          testID={`${testID}-arrow`}
        >
          <Image source={theme.isDark ? arrowDark : arrowLight} style={styles.arrow} />
        </View>
      )}
    </View>
  );
};

// Sizes and offsets from the 360-wide Figma frame.
const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 24,
    paddingHorizontal: 16,
  },
  paper: {
    width: 147,
    height: 182,
  },
  text: {
    width: '100%',
    maxWidth: 290,
    marginTop: 27,
    gap: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: '500',
    lineHeight: 30,
    letterSpacing: -0.1,
    textAlign: 'center',
  },
  body: {
    fontSize: 16,
    fontWeight: '500',
    lineHeight: 24,
    textAlign: 'center',
  },
  arrowBox: {
    width: 142,
    height: 160,
    marginTop: -7.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrow: {
    width: 127,
    height: 146,
    transform: [{ rotate: '-7.91deg' }],
  },
});

export default EmptyState;
