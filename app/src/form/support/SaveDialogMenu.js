import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal, Pressable } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const SaveDialogMenu = ({ visible, setVisible, handleOnSaveAndExit, handleOnExit }) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={() => setVisible(false)}
      testID="save-dialog-menu"
    >
      <Pressable style={styles.overlay} onPress={() => setVisible(false)}>
        <Pressable style={[styles.sheet, { backgroundColor: theme.bg.surfaceElevated1 }]} onPress={() => {}}>
          <View style={styles.handle} />
          <Text style={[styles.title, { color: theme.text.primary }]}>
            {trans.leaveSubmissionTitle || 'Leave this submission?'}
          </Text>

          <TouchableOpacity
            style={styles.optionRow}
            testID="save-and-exit-button"
            onPress={() => {
              if (handleOnSaveAndExit) {
                handleOnSaveAndExit();
              }
            }}
          >
            <Icon name="time-outline" size={24} color={theme.text.primary} style={styles.optionIcon} />
            <View style={styles.optionContent}>
              <Text style={[styles.optionTitle, { color: theme.text.primary }]}>
                {trans.buttonSaveNExit}
              </Text>
              <Text style={[styles.optionDesc, { color: theme.text.secondary }]}>
                {trans.saveDraftDesc || 'Keeps your progress. Reopen it from the drafts list.'}
              </Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.optionRow}
            testID="exit-without-saving-button"
            onPress={() => {
              if (handleOnExit) {
                handleOnExit();
              }
            }}
          >
            <Icon name="close" size={24} color={theme.status.error} style={styles.optionIcon} />
            <View style={styles.optionContent}>
              <Text style={[styles.optionTitle, { color: theme.status.error }]}>
                {trans.buttonExitWoSaving}
              </Text>
              <Text style={[styles.optionDesc, { color: theme.text.secondary }]}>
                {trans.exitWithoutSavingDesc || 'Discards everything you have typed in this submission.'}
              </Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.cancelButton}
            testID="cancel-button"
            onPress={() => setVisible(false)}
          >
            <Text style={[styles.cancelText, { color: theme.text.secondary }]}>
              {trans.buttonCancel}
            </Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'flex-end',
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 24,
    paddingBottom: 34,
    paddingTop: 12,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#999',
    alignSelf: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 16,
    marginBottom: 12,
  },
  optionIcon: {
    marginRight: 14,
  },
  optionContent: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  optionDesc: {
    fontSize: 14,
    lineHeight: 20,
  },
  cancelButton: {
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 4,
  },
  cancelText: {
    fontSize: 16,
    fontWeight: '500',
  },
});

export default SaveDialogMenu;
