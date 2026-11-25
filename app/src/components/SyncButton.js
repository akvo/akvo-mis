import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../store';
import i18n from '../lib/i18n';
import useTheme from '../lib/theme';

/**
 * Floating sync button on Home (APP-585). Replaces the bottom Sync tab: a tab press
 * implies navigating away, but sync stays on Home. Behaviour is unchanged — the guards
 * (offline, in-progress) live here and Home's onPress reuses the existing sync path.
 * Purely presentational; Home passes all state in.
 */
const SyncButton = ({
  pending = 0,
  online = true,
  syncing = false,
  onPress = null,
  testID = 'home-sync-button',
}) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const disabled = !online || syncing;

  const label = (() => {
    if (!online) {
      return trans.offlineText;
    }
    if (syncing) {
      return trans.syncingText;
    }
    return pending > 0 ? `${trans.syncDataPointBtn} (${pending})` : trans.syncDataPointBtn;
  })();

  return (
    <TouchableOpacity
      style={[styles.button, { backgroundColor: disabled ? theme.text.tertiary : theme.text.highlight }]}
      onPress={disabled ? null : onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      accessibilityLabel={label}
      testID={testID}
    >
      <Icon name={online ? 'sync' : 'cloud-offline-outline'} size={26} color="#FFFFFF" />
      {online && !syncing && pending > 0 && (
        <View style={[styles.badge, { backgroundColor: '#FFFFFF', borderColor: theme.text.highlight }]}>
          <Text style={[styles.badgeText, { color: theme.text.highlight }]} numberOfLines={1}>
            {pending > 99 ? '99+' : pending}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    position: 'absolute',
    right: 16,
    bottom: 16,
    width: 60,
    height: 60,
    borderRadius: 30,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    paddingHorizontal: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '700',
  },
});

export default SyncButton;
