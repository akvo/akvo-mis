import React from 'react';
import { StyleSheet } from 'react-native';
import { Dialog } from '@rneui/themed';
import { UIState } from '../../store';
import { i18n } from '../../lib';

const SaveDialogMenu = ({ visible, setVisible, handleOnSaveAndExit, handleOnExit }) => {
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  return (
    <Dialog visible={visible} testID="save-dialog-menu" overlayStyle={styles.dialogMenuContainer}>
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
        buttonStyle={styles.buttonDanger}
        titleStyle={styles.textDanger}
        onPress={() => {
          if (handleOnExit) {
            handleOnExit();
          }
        }}
      />
      {/*
        Clear, not outline: Cancel is the way out, not a fifth thing to weigh. As an
        outline button it read with the same weight as "Save and send to web
        dashboard" directly above it.
      */}
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
    // Sized by its contents. `flex: 0.2` pinned the overlay to a fifth of the screen
    // regardless of how many buttons it held, so the last one was clipped as soon as
    // a fourth was added.
    flexDirection: 'column',
    gap: 10,
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderRadius: 0,
  },
  buttonDanger: {
    borderColor: '#D63D39',
  },
  textDanger: {
    color: '#D63D39',
  },
});

export default SaveDialogMenu;
