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
      overlayStyle={[styles.dialogMenuContainer, { backgroundColor: theme.bg.surfaceElevated1 }]}
    >
      <Dialog.Title title={trans.unsavedChangesTitle} titleStyle={{ color: theme.text.primary }} />
      <Dialog.Button
        type="solid"
        title={trans.buttonSaveNExit}
        testID="save-and-exit-button"
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
        buttonStyle={{ borderColor: theme.status.error }}
        titleStyle={{ color: theme.status.error }}
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
    borderRadius: 0,
  },
});

export default SaveDialogMenu;
