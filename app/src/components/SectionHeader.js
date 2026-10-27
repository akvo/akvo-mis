import React, { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import useTheme from '../lib/theme';

/**
 * Collapsible section title. Collapsing hides `children`; the state lives only as
 * long as the screen does (A14), so reopening the screen shows it expanded again.
 * Pass `collapsed` + `onToggle` to own the state instead, e.g. as a SectionList
 * header, where the list drops the section's rows itself (A19).
 */
const SectionHeader = ({
  title,
  count = null,
  children = null,
  style = null,
  testID = 'section-header',
  collapsed: controlledCollapsed = false,
  onToggle = null,
}) => {
  const [ownCollapsed, setOwnCollapsed] = useState(false);
  const collapsed = onToggle ? controlledCollapsed : ownCollapsed;
  const theme = useTheme();
  return (
    <View style={style}>
      <TouchableOpacity
        style={styles.header}
        onPress={onToggle || (() => setOwnCollapsed((prev) => !prev))}
        testID={testID}
        accessibilityRole="button"
        accessibilityState={{ expanded: !collapsed }}
      >
        <Text style={[styles.title, { color: theme.text.primary }]} numberOfLines={1}>
          {title}
        </Text>
        {count !== null && (
          <Text style={[styles.count, { color: theme.text.tertiary }]}>{count}</Text>
        )}
        <Icon
          name={collapsed ? 'chevron-down' : 'chevron-up'}
          size={20}
          color={theme.icon.secondary}
        />
      </TouchableOpacity>
      {!collapsed && children}
    </View>
  );
};

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  title: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
    lineHeight: 24,
  },
  count: {
    fontSize: 14,
    lineHeight: 20,
  },
});

export default SectionHeader;
