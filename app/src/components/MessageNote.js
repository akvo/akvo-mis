import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

/**
 * Figma "Message Note": an icon beside one or more lines of 12px text on an elevated card.
 * `info` reads as guidance; `danger` colors icon and text as an error. With `onPress`
 * the whole card is the touch target.
 */
const MessageNote = ({ tone = 'info', icon = null, lines = [], onPress = null, testID = null }) => {
  const theme = useTheme();
  const danger = tone === 'danger';
  const textColor = danger ? theme.input.errorText : theme.text.secondary;
  const iconColor = danger ? theme.input.errorText : theme.icon.accent;
  const Container = onPress ? TouchableOpacity : View;
  return (
    <Container
      style={[styles.card, { backgroundColor: theme.bg.surfaceElevated3 }]}
      onPress={onPress}
      testID={testID}
      accessibilityRole={onPress ? 'button' : null}
    >
      <Icon
        name={icon || (danger ? 'refresh' : 'information-circle')}
        size={24}
        color={iconColor}
      />
      <View style={styles.text}>
        {lines.map((line) => (
          <Text key={line} style={[styles.line, { color: textColor }]}>
            {line}
          </Text>
        ))}
      </View>
    </Container>
  );
};

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 12,
    borderRadius: 16,
  },
  text: {
    flex: 1,
  },
  line: {
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 16,
    letterSpacing: 0.04,
  },
});

export default MessageNote;
