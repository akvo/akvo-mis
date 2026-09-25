import React, { useMemo } from 'react';
import { View } from 'react-native';
import { Dropdown } from 'react-native-element-dropdown';
import { FieldLabel, OptionItem } from '../support';
import getStyles from '../styles';
import { FormState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const TypeOption = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  option = [],
  tooltip = null,
  requiredSign = '*',
  disabled = false,
  hasError = false,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const showSearch = useMemo(() => option.length > 3, [option]);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;
  const color = useMemo(() => {
    const currentValue = value?.[0];
    return option.find((x) => x.value === currentValue)?.color;
  }, [value, option]);

  const selectedStyle = useMemo(() => {
    const currentValue = value?.[0];
    const backgroundColor = option.find((x) => x.value === currentValue)?.color;
    if (!color) {
      return {};
    }
    return {
      marginLeft: -8,
      marginRight: -27,
      borderRadius: 5,
      paddingTop: 8,
      paddingLeft: 8,
      paddingBottom: 8,
      color: '#FFF',
      backgroundColor,
    };
  }, [value, color, option]);
  const style = {
    ...styles.dropdownField,
    ...(disabled ? styles.dropdownFieldDisabled : {}),
    ...(hasError ? styles.inputFieldError : {}),
  };

  return (
    <View style={styles.optionContainer}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Dropdown
        style={style}
        selectedTextStyle={[selectedStyle, !color && { color: theme.input.textInput }]}
        containerStyle={{
          backgroundColor: theme.bg.surfaceElevated1,
          borderRadius: 12,
        }}
        data={option}
        search={showSearch}
        maxHeight={500}
        labelField="label"
        valueField="value"
        searchPlaceholder={trans.searchPlaceholder}
        value={value?.[0] || ''}
        onChange={({ value: optValue }) => {
          if (onChange) {
            onChange(id, [optValue]);
          }
        }}
        renderItem={(item, selected) => <OptionItem {...item} selected={selected} />}
        testID="type-option-dropdown"
        placeholder={trans.selectItem}
        placeholderStyle={{ color: theme.input.text }}
        inputSearchStyle={{
          borderRadius: 12,
          backgroundColor: theme.bg.surfaceTertiary,
          borderColor: 'transparent',
          color: theme.text.primary,
          paddingHorizontal: 12,
        }}
        disable={disabled}
      />
    </View>
  );
};

export default TypeOption;
