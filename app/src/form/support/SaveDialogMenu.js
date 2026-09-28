import React from 'react';
import { StyleSheet } from 'react-native';
import { Dialog } from '@rneui/themed';
import { UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const SaveDialogMenu = ({ visible, setVisible, handleOnSaveAndExit, handleOnExit }) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  return (
    <Dialog
      visible={visible}
      testID="save-dialog-menu"
      overlayStyle={[
        styles.dialogMenuContainer,
        { backgroundColor: theme.bg.surfaceElevated1, borderRadius: theme.radius.lg },
      ]}
    >
      <Dialog.Title title={trans.unsavedChangesTitle} titleStyle={{ color: theme.text.primary }} />
      <Dialog.Button
        type="solid"
        title={trans.buttonSaveNExit}
        testID="save-and-exit-button"
        buttonStyle={[styles.button, { backgroundColor: theme.buttonPrimary.bg }]}
        titleStyle={[styles.buttonTitle, { color: theme.buttonPrimary.text }]}
        onPress={() => {
          if (handleOnSaveAndExit) {
            handleOnSaveAndExit();
          }
        }}
      />
      <Dialog.Button
        type="outline"
        title={trans.buttonSaveNSendToWeb}
        testID="save-and-send-to-web-button"
        buttonStyle={[styles.button, { borderColor: theme.buttonTertiary.border }]}
        titleStyle={[styles.buttonTitle, { color: theme.buttonTertiary.text }]}
        onPress={() => {
          if (handleOnSaveAndExit) {
            handleOnSaveAndExit({ sendToWeb: true });
          }
        }}
      />
      <Dialog.Button
        type="outline"
        title={trans.buttonExitWoSaving}
        testID="exit-without-saving-button"
        buttonStyle={[styles.button, { borderColor: theme.status.error }]}
        titleStyle={[styles.buttonTitle, { color: theme.status.error }]}
        onPress={() => {
          if (handleOnExit) {
            handleOnExit();
          }
        }}
      />
      <Dialog.Button
        type="clear"
        title={trans.buttonCancel}
        testID="cancel-button"
        buttonStyle={styles.button}
        titleStyle={[styles.buttonTitle, { color: theme.buttonGhost.color }]}
        onPress={() => {
          setVisible(false);
        }}
      />
    </Dialog>
  );
};

const styles = StyleSheet.create({
  dialogMenuContainer: {
    flexDirection: 'column',
    gap: 10,
    paddingVertical: 20,
    paddingHorizontal: 16,
  },
  button: {
    borderRadius: 24,
    paddingVertical: 12,
  },
  buttonTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
});

export default SaveDialogMenu;
