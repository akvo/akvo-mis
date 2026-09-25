/* eslint-disable react/jsx-props-no-spreading */
import React, { isValidElement } from 'react';
import { View } from 'react-native';
import { Input, Text } from '@rneui/themed';
import { FieldLabel } from '../support';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

export const addPreffix = (addonBefore, theme) => {
  if (!addonBefore) {
    return {};
  }
  const testID = 'field-preffix';
  let element = addonBefore;
  if (element && isValidElement(element)) {
    element = <View testID={testID}>{element}</View>;
  }
  if (element && !isValidElement(element)) {
    element = <Text testID={testID}>{element}</Text>;
  }
  return {
    leftIcon: element,
    leftIconContainerStyle: {
      backgroundColor: theme.bg.surfaceTertiary,
      marginLeft: -16,
      marginRight: 10,
      marginVertical: 0,
      paddingLeft: 12,
      paddingRight: 12,
      borderWidth: 0,
      borderTopLeftRadius: 12,
      borderBottomLeftRadius: 12,
      borderTopRightRadius: 0,
      borderBottomRightRadius: 0,
    },
  };
};

export const addSuffix = (addonAfter, theme) => {
  if (!addonAfter) {
    return {};
  }
  const testID = 'field-suffix';
  let element = addonAfter;
  if (element && isValidElement(element)) {
    element = <View testID={testID}>{element}</View>;
  }
  if (element && !isValidElement(element)) {
    element = <Text testID={testID}>{element}</Text>;
  }
  return {
    rightIcon: element,
    rightIconContainerStyle: {
      backgroundColor: theme.bg.surfaceTertiary,
      marginRight: -16,
      marginLeft: 10,
      marginVertical: 0,
      paddingLeft: 12,
      paddingRight: 12,
      borderWidth: 0,
      borderTopRightRadius: 12,
      borderBottomRightRadius: 12,
      borderTopLeftRadius: 0,
      borderBottomLeftRadius: 0,
    },
  };
};

const TypeInput = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  requiredSign = '*',
  meta_uuid: metaUUID,
  disabled = false,
  addonAfter = null,
  addonBefore = null,
  tooltip = null,
  onFocus = null,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const requiredValue = required ? requiredSign : null;
  const inputContainerStyle =
    metaUUID || disabled
      ? { ...styles.inputFieldContainer, ...styles.inputFieldDisabled }
      : styles.inputFieldContainer;

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
        errorStyle={{ height: 0, margin: 0 }}
        onChangeText={(val) => {
          if (onChange) {
            onChange(id, val);
          }
        }}
        value={value}
        testID="type-input"
        onFocus={handleFocus}
        placeholderTextColor={theme.input.text}
        {...addPreffix(addonBefore, theme)}
        {...addSuffix(addonAfter, theme)}
        disabled={metaUUID || disabled}
      />
    </View>
  );
};

export default TypeInput;
