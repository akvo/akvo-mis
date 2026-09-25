import React, { useRef, useState } from 'react';
import { View, StyleSheet, Image, Modal } from 'react-native';
import SignatureCanvas from 'react-native-signature-canvas';
import { Button, Icon } from '@rneui/themed';
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
        <View style={[styles.preview, { backgroundColor: theme.bg.surfaceTertiary }]}>
          <Image
            resizeMode="contain"
            style={{ width: '100%', height: 164 }}
            source={{ uri: signature }}
          />
        </View>
      )}
      <Button
        title={signature ? trans.changeSignatureButton : trans.openSignatureButton}
        onPress={() => setShow(true)}
        icon={<Icon name="create" size={20} color={theme.buttonPrimary.text} type="ionicon" />}
        style={{ width: '100%' }}
        containerStyle={{ marginTop: 10 }}
        testID="open-signature-button"
        accessibilityLabel="open-signature-button"
      />
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
});
