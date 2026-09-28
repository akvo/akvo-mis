import React, { useState } from 'react';
import { Input, Slider, Text } from '@rneui/themed';
import { Dropdown } from 'react-native-element-dropdown';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../../store';
import { i18n } from '../../lib';
import { ConfirmDialog } from '../../components';

const DialogForm = ({ onOk, onCancel, showDialog, edit, initValue = 0 }) => {
  const [value, setValue] = useState(initValue);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const { type, label, slider, value: defaultValue, options, description } = edit || {};
  const isPassword = type === 'password' || false;

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
          trackStyle={{ height: 5, backgroundColor: '#2089dc' }}
          thumbStyle={{ height: 20, width: 20, backgroundColor: '#2089dc' }}
          thumbProps={{
            children: <Icon name="ellipse" size={20} color="#2089dc" />,
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
          testID="settings-form-dropdown"
        />
      )}
      {description?.name && <Text>{i18n.transform(activeLang, description)?.name}</Text>}
    </ConfirmDialog>
  );
};

export default DialogForm;
