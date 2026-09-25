import React from 'react';
import { View, Text } from 'react-native';
import Icon from 'react-native-vector-icons/FontAwesome';
import useTheme from '../../lib/theme';

const OptionItem = ({ label, name, color, selected, isMulti }) => {
  const theme = useTheme();
  const textColor = color ? '#ffffff' : theme.text.primary;
  const iconColor = color ? '#ffffff' : selected ? theme.icon.primary : theme.text.tertiary;
  return (
    <View style={{ padding: 3 }}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          padding: 10,
          backgroundColor: color || (selected ? theme.bg.surfaceTranslucent : theme.bg.surfaceSecondary),
          borderRadius: color ? 8 : 0,
        }}
      >
        {isMulti && (
          <Icon
            name={selected ? 'check-square' : 'square-o'}
            size={18}
            color={iconColor}
            style={{ marginRight: 10 }}
          />
        )}
        <Text style={{ color: textColor, flex: 1, fontSize: 15 }}>{label || name}</Text>
      </View>
    </View>
  );
};

export default OptionItem;
