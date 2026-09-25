import React from 'react';
import { View, Modal, TouchableOpacity, StyleSheet, Pressable } from 'react-native';
import { Text } from '@rneui/themed';
import useTheme from '../lib/theme';

const ConfirmDialog = ({
  visible = false,
  title,
  message,
  actions = [],
  onClose,
  children,
  testID,
  danger = false,
}) => {
  const theme = useTheme();
  const titleColor = danger ? theme.status.error : theme.text.primary;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      testID={testID}
    >
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable
          style={[styles.card, { backgroundColor: theme.bg.surfaceElevated1 }]}
          onPress={() => {}}
        >
          {title && (
            <Text style={[styles.title, { color: titleColor }]}>{title}</Text>
          )}
          {message && (
            <Text style={[styles.message, { color: theme.text.primary }]}>{message}</Text>
          )}
          {children}
          {actions.length > 0 && (
            <View style={styles.buttonRow}>
              {actions.map((action) => {
                const isPrimary = action.type === 'primary';
                const isDanger = action.type === 'danger';
                const buttonBg = isPrimary
                  ? theme.buttonPrimary.bg
                  : isDanger
                    ? theme.status.error
                    : theme.buttonSecondary.bg;
                const buttonText = isPrimary || isDanger
                  ? theme.buttonPrimary.text
                  : theme.buttonSecondary.text;
                return (
                  <TouchableOpacity
                    key={action.label}
                    style={[styles.button, { backgroundColor: buttonBg, flex: 1 }]}
                    onPress={action.onPress}
                    testID={action.testID}
                  >
                    <Text style={[styles.buttonText, { color: buttonText }]}>
                      {action.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  card: {
    width: '100%',
    borderRadius: 20,
    paddingVertical: 24,
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '400',
    marginBottom: 12,
  },
  message: {
    fontSize: 16,
    lineHeight: 22,
    marginBottom: 20,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  button: {
    paddingVertical: 14,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '700',
  },
});

export default ConfirmDialog;
