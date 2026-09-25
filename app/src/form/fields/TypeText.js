import React from 'react';
import { View } from 'react-native';
import { Input } from '@rneui/themed';
import { FieldLabel } from '../support';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

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
  const theme = useTheme();
  const styles = getStyles(theme);
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
        inputStyle={{ color: theme.input.textInput }}
        multiline
        numberOfLines={4}
        style={{ textAlignVertical: 'top', color: theme.input.textInput }}
        onChangeText={(val) => {
          if (onChange) {
            onChange(id, val);
          }
        }}
        onFocus={handleFocus}
        value={value}
        testID="type-text"
        placeholderTextColor={theme.input.text}
        disabled={metaUUID || disabled}
        errorStyle={{ height: 0, margin: 0 }}
      />
    </View>
  );
};

export default TypeText;
