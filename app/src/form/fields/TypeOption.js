import React, { useMemo, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Dropdown } from 'react-native-element-dropdown';
import { FieldLabel, OptionItem } from '../support';
import getStyles from '../styles';
import { FormState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';
import useDropdownPlacement from '../lib/dropdown-placement';

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
  const anchor = useRef(null);
  const { placement, place } = useDropdownPlacement();
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
      color: theme.buttonPrimary.text,
      backgroundColor,
    };
  }, [value, color, option]);
  const style = {
    ...styles.dropdownField,
    ...(disabled ? styles.dropdownFieldDisabled : {}),
    ...(hasError ? styles.inputFieldError : {}),
  };

  const isTwoOption = option.length === 2;

  if (isTwoOption) {
    const selectedValue = value?.[0] || '';
    return (
      <View style={styles.optionContainer}>
        <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
        <View style={[pillStyles.container, { backgroundColor: theme.input.bg }]}>
          {option.map((opt) => {
            const isSelected = opt.value === selectedValue;
            return (
              <TouchableOpacity
                key={opt.value}
                style={[pillStyles.pill, isSelected && { backgroundColor: theme.buttonPrimary.bg }]}
                onPress={() => {
                  if (onChange && !disabled) {
                    onChange(id, [opt.value]);
                  }
                }}
                disabled={disabled}
                testID={`type-option-pill-${opt.value}`}
              >
                <Text
                  style={[
                    pillStyles.pillText,
                    {
                      color: isSelected ? theme.buttonPrimary.text : theme.text.primary,
                      fontWeight: isSelected ? '600' : '500',
                    },
                  ]}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.optionContainer}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View ref={anchor} collapsable={false}>
        <Dropdown
          style={style}
          dropdownPosition={placement.dropdownPosition}
          onFocus={() => place(anchor)}
          selectedTextStyle={[selectedStyle, !color && { color: theme.input.textInput }]}
          containerStyle={{
            backgroundColor: theme.bg.surfaceElevated1,
            borderRadius: 12,
          }}
          data={option}
          search={showSearch}
          maxHeight={placement.maxHeight}
          labelField="label"
          valueField="value"
          searchPlaceholder={trans.searchPlaceholder}
          value={value?.[0] || ''}
          onChange={({ value: optValue }) => {
            if (onChange) {
              onChange(id, [optValue]);
            }
          }}
          renderItem={(item, selected) => (
            <OptionItem
              label={item.label}
              name={item.name}
              color={item.color}
              selected={selected}
            />
          )}
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
    </View>
  );
};

const pillStyles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderRadius: 28,
    padding: 4,
    marginHorizontal: 10,
  },
  pill: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 24,
  },
  pillText: {
    fontSize: 14,
  },
});

export default TypeOption;
