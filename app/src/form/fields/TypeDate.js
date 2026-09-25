import React, { useState } from 'react';
import { View } from 'react-native';
import moment from 'moment';
import { Input } from '@rneui/themed';
import DateTimePicker from '@react-native-community/datetimepicker';
import { FieldLabel } from '../support';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

const TypeDate = ({
  onChange,
  value,
  keyform,
  id,
  label,
  required,
  requiredSign = '*',
  disabled = false,
  tooltip = null,
  onFocus = null,
  hasError = false,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);
  const [showDatepicker, setShowDatePicker] = useState(false);

  const getDate = (v) =>
    typeof v === 'string' ? moment(v, 'YYYY-MM-DD').toDate() : v || new Date();

  const datePickerValue = getDate(value);
  const requiredValue = required ? requiredSign : null;
  const dateValue = value ? moment(value).format('YYYY-MM-DD') : value;

  const handleFocus = () => {
    if (onFocus) {
      onFocus();
    }
  };

  return (
    <View>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <Input
                inputContainerStyle={{
          ...styles.inputFieldContainer,
          ...(hasError ? styles.inputFieldError : {}),
        }}
        inputStyle={{ color: theme.input.textInput }}
        onPressIn={() => setShowDatePicker(true)}
        onFocus={handleFocus}
        showSoftInputOnFocus={false}
        testID="type-date"
        value={dateValue}
        placeholderTextColor={theme.input.text}
        disabled={disabled}
        renderErrorMessage={false}
      />
      {showDatepicker && (
        <DateTimePicker
          testID="date-time-picker"
          value={datePickerValue}
          mode="date"
          onChange={({ nativeEvent: val }) => {
            setShowDatePicker(false);
            if (onChange) {
              onChange(id, new Date(val.timestamp));
            }
          }}
        />
      )}
    </View>
  );
};

export default TypeDate;
