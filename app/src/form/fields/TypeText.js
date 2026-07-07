import React from 'react';
import { View } from 'react-native';
import { Input } from '@rneui/themed';
import { FieldLabel } from '../support';
import styles from '../styles';

const TypeText = ({
  onChange,
  value,
  keyform,
  id,
  label,
  tooltip,
  required,
  requiredSign = '*',
  meta_uuid: metaUUID,
  disabled,
  onFocus = null,
}) => {
  const requiredValue = required ? requiredSign : null;
  const inputContainerStyle =
    metaUUID || disabled
      ? { ...styles.textAreaContainer, ...styles.inputFieldDisabled }
      : styles.textAreaContainer;

  const handleFocus = () => {
    if (onFocus) {
      onFocus();
    }
  };

  return (
    <View>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Input
        inputContainerStyle={inputContainerStyle}
        multiline
        numberOfLines={4}
        style={{ textAlignVertical: 'top' }}
        onChangeText={(val) => {
          if (onChange) {
            onChange(id, val);
          }
        }}
        onFocus={handleFocus}
        value={value}
        testID="type-text"
        disabled={metaUUID || disabled}
      />
    </View>
  );
};

export default TypeText;
