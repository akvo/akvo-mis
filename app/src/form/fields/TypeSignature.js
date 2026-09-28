import React, { useRef, useState } from 'react';
import { View, StyleSheet, Image, Modal, TouchableOpacity, Text } from 'react-native';
import SignatureCanvas from 'react-native-signature-canvas';
import { Icon } from '@rneui/themed';
import { FieldLabel } from '../support';
import { FormState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const TypeSignature = ({
  onChange,
  keyform,
  id,
  value,
  label,
  required,
  requiredSign = '*',
  tooltip = null,
}) => {
  const theme = useTheme();
  const [show, setShow] = useState(false);
  const [signature, setSignature] = useState(value);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const ref = useRef();

  const handleSignature = (data) => {
    onChange(id, data);
    setSignature(data);
    setShow(false);
  };

  const handleClear = () => {
    onChange(id, null);
    setSignature(null);
  };

  // The canvas is a text-field-like surface; its bg is baked into the saved PNG.
  const penColor = theme.input.textInput;
  const canvasBg = theme.input.bg;
  // Injected after the library's default CSS (react-native-signature-canvas h5/html.js).
  const webStyle = `
    body, html { height: 100%; background-color: ${theme.bg.surfacePrimary}; font-family: Inter, sans-serif; }
    .m-signature-pad { display: flex; flex-direction: column; border: none; box-shadow: none; background-color: transparent; }
    .m-signature-pad--body { flex: none; height: 50vh; overflow: hidden; border: 1px solid ${theme.input.border}; border-radius: ${theme.radius.md}px; background-color: ${canvasBg}; }
    .m-signature-pad--footer { flex: none; height: 48px; margin-top: ${theme.spacing.lg}px; padding: 0; }
    .m-signature-pad--footer .description { color: ${theme.text.tertiary}; font-size: ${theme.typography.size.sm}px; }
    .m-signature-pad--footer .button { height: 44px; line-height: 42px; padding: 0 ${theme.spacing.xl}px; border-radius: ${theme.radius.xl}px; font-size: ${theme.typography.size.md}px; font-weight: 600; }
    .m-signature-pad--footer .button.clear { background-color: transparent; color: ${theme.buttonTertiary.text}; border: 1px solid ${theme.buttonTertiary.border}; }
    .m-signature-pad--footer .button.save { background-color: ${theme.buttonPrimary.bg}; color: ${theme.buttonPrimary.text}; }
  `;

  return (
    <View style={styles.container}>
      <FieldLabel
        keyform={keyform}
        name={label}
        required={required}
        requiredSign={requiredSign}
        tooltip={tooltip}
      />
      {signature && (
        <View
          style={[styles.preview, { backgroundColor: canvasBg, borderRadius: theme.radius.md }]}
        >
          <Image
            resizeMode="contain"
            style={{ width: '100%', height: 164 }}
            source={{ uri: signature }}
          />
        </View>
      )}
      <TouchableOpacity
        style={[styles.signButton, { backgroundColor: theme.buttonPrimary.bg }]}
        onPress={() => setShow(true)}
        testID="open-signature-button"
        accessibilityLabel="open-signature-button"
      >
        <Icon name="create" size={18} color={theme.buttonPrimary.text} type="ionicon" />
        <Text style={[styles.signButtonText, { color: theme.buttonPrimary.text }]}>
          {signature ? trans.changeSignatureButton : trans.openSignatureButton}
        </Text>
      </TouchableOpacity>
      {show && (
        <Modal onRequestClose={() => setShow(false)}>
          <View
            style={[
              styles.modalBody,
              { backgroundColor: theme.bg.surfacePrimary, padding: theme.spacing.lg },
            ]}
          >
            <SignatureCanvas
              ref={ref}
              onOK={handleSignature}
              onClear={handleClear}
              descriptionText={trans.signHereText}
              clearText={trans.clearText}
              confirmText={trans.confirmText}
              autoClear={false}
              dataURL={signature}
              imageType="image/png"
              backgroundColor={canvasBg}
              penColor={penColor}
              webStyle={webStyle}
              webviewContainerStyle={{ backgroundColor: theme.bg.surfacePrimary }}
            />
          </View>
        </Modal>
      )}
    </View>
  );
};

export default TypeSignature;

const styles = StyleSheet.create({
  container: {
    marginBottom: 10,
    flexDirection: 'column',
  },
  modalBody: {
    flex: 1,
  },
  preview: {
    width: '100%',
    height: 164,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 15,
  },
  signButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 24,
    marginTop: 10,
    marginHorizontal: 10,
    gap: 8,
  },
  signButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
});
