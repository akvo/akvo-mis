import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Input, Slider, Text } from '@rneui/themed';
import { Dropdown } from 'react-native-element-dropdown';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';
import { ConfirmDialog, LevelIcon } from '../../components';

const DialogForm = ({ onOk, onCancel, showDialog, edit, initValue = 0 }) => {
  const [value, setValue] = useState(initValue);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);
  const theme = useTheme();

  const { type, label, slider, value: defaultValue, options, description, levelKind } = edit || {};
  const isPassword = type === 'password' || false;
  const inputColors = {
    inputStyle: { color: theme.input.textInput },
    inputContainerStyle: { borderBottomColor: theme.input.border },
    placeholderTextColor: theme.input.text,
  };

  const renderOption = (item, selected) => (
    <View style={[styles.option, selected && { backgroundColor: theme.bg.surfaceChip }]}>
      {levelKind && <LevelIcon kind={levelKind} level={item.value} size={20} />}
      <Text style={[styles.optionText, { color: theme.text.primary }]}>{item.label}</Text>
    </View>
  );

  return (
    <ConfirmDialog
      visible={showDialog}
      testID="settings-form-dialog"
      onClose={onCancel}
      actions={[
        {
          label: trans.buttonCancel,
          type: 'secondary',
          onPress: onCancel,
          testID: 'settings-form-dialog-cancel',
        },
        {
          label: trans.buttonOk,
          type: 'primary',
          onPress: () => onOk(value),
          testID: 'settings-form-dialog-ok',
        },
      ]}
    >
      {type === 'slider' && (
        <Slider
          // eslint-disable-next-line react/jsx-props-no-spreading
          {...slider}
          allowTouchTrack
          onValueChange={setValue}
          trackStyle={[styles.sliderTrack, { backgroundColor: theme.buttonPrimary.bg }]}
          thumbStyle={[styles.sliderThumb, { backgroundColor: theme.buttonPrimary.bg }]}
          thumbProps={{
            children: <Icon name="ellipse" size={20} color={theme.buttonPrimary.bg} />,
          }}
          testID="settings-form-slider"
        />
      )}
      {['text', 'number', 'password'].includes(type) && (
        <Input
          placeholder={label}
          secureTextEntry={isPassword}
          onChangeText={setValue}
          defaultValue={defaultValue?.toString()}
          testID="settings-form-input"
          keyboardType={type === 'number' ? 'number-pad' : 'default'}
          inputStyle={inputColors.inputStyle}
          inputContainerStyle={inputColors.inputContainerStyle}
          placeholderTextColor={inputColors.placeholderTextColor}
        />
      )}
      {type === 'dropdown' && (
        <Dropdown
          data={options}
          maxHeight={300}
          labelField="label"
          valueField="value"
          placeholder={label}
          value={value}
          onChange={(item) => {
            setValue(item.value);
          }}
          renderItem={renderOption}
          renderLeftIcon={() =>
            levelKind ? <LevelIcon kind={levelKind} level={value} size={20} /> : null
          }
          style={[
            styles.dropdown,
            { backgroundColor: theme.input.bg, borderColor: theme.input.border },
          ]}
          placeholderStyle={{ color: theme.input.text }}
          selectedTextStyle={[levelKind && styles.selectedText, { color: theme.input.textInput }]}
          containerStyle={{ backgroundColor: theme.bg.surfaceElevated1 }}
          iconColor={theme.icon.secondary}
          testID="settings-form-dropdown"
        />
      )}
      {description?.name && (
        <Text style={[styles.description, { color: theme.text.secondary }]}>
          {i18n.transform(activeLang, description)?.name}
        </Text>
      )}
    </ConfirmDialog>
  );
};

const styles = StyleSheet.create({
  sliderTrack: {
    height: 5,
  },
  sliderThumb: {
    height: 20,
    width: 20,
  },
  dropdown: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  selectedText: {
    marginLeft: 8,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  optionText: {
    fontSize: 16,
  },
  description: {
    marginTop: 8,
  },
});

export default DialogForm;
