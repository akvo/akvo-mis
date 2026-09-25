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

  const penColor = theme.isDark ? '#FFFFFF' : '#000000';
  const canvasBg = theme.isDark ? theme.bg.surfaceTertiary : '#FFFFFF';

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
        <View style={[styles.preview, { backgroundColor: theme.bg.surfaceTertiary, borderRadius: 12 }]}>
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
        <Modal>
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
          />
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
