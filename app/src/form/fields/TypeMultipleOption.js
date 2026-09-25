import React from 'react';
import { View, Text } from 'react-native';
import { MultiSelect } from 'react-native-element-dropdown';
import Icon from 'react-native-vector-icons/Ionicons';
import { FieldLabel, OptionItem } from '../support';
import getStyles from '../styles';
import { FormState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const TypeMultipleOption = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  requiredSign = '*',
  disabled = false,
  option = [],
  tooltip = null,
  hasError = false,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const showSearch = React.useMemo(() => option.length > 3, [option]);
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const requiredValue = required ? requiredSign : null;
  const style = {
    ...styles.dropdownField,
    ...(disabled ? styles.dropdownFieldDisabled : {}),
    ...(hasError ? styles.inputFieldError : {}),
  };

  return (
    <View style={styles.multipleOptionContainer}>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <MultiSelect
        style={style}
        selectedStyle={styles.dropdownSelectedList}
        containerStyle={{
          backgroundColor: theme.bg.surfaceElevated1,
          borderRadius: 12,
        }}
        activeColor={theme.bg.surfaceTranslucent}
        data={option}
        search={showSearch}
        maxHeight={500}
        labelField="label"
        valueField="value"
        searchPlaceholder={trans.searchPlaceholder}
        placeholder={trans.selectMultiItem}
        placeholderStyle={{ color: theme.input.text }}
        inputSearchStyle={{
          borderRadius: 12,
          backgroundColor: theme.bg.surfaceTertiary,
          borderColor: 'transparent',
          color: theme.text.primary,
          paddingHorizontal: 12,
        }}
        value={value || []}
        onChange={(v) => {
          if (onChange) {
            onChange(id, v);
          }
        }}
        renderItem={(item, selected) => <OptionItem {...item} selected={selected} isMulti />}
        renderSelectedItem={({ color, label: labelText, name }) => {
          const bgColor = color || theme.bg.surfaceChip;
          const textColor = color ? '#fff' : theme.text.primary;
          return (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                backgroundColor: bgColor,
                paddingHorizontal: 12,
                paddingVertical: 8,
                marginLeft: 10,
                marginTop: 5,
                borderRadius: 12,
              }}
            >
              <Text style={{ color: textColor, fontWeight: color ? 'bold' : 'normal' }}>
                {labelText || name}
              </Text>
              <Icon name="close-circle" size={14} color={textColor} style={{ marginLeft: 6 }} />
            </View>
          );
        }}
        testID="type-multiple-option-dropdown"
        confirmUnSelectItem
        disable={disabled}
      />
    </View>
  );
};

export default TypeMultipleOption;
