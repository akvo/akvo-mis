import React from 'react';
import { TouchableOpacity, View } from 'react-native';
import { Text, Icon } from '@rneui/themed';
import getStyles from '../styles';
import { FormState } from '../../store';
import useTheme from '../../lib/theme';

const FieldGroupHeader = ({ description, index, label, repeatable, id }) => {
  const theme = useTheme();
  const styles = getStyles(theme);

  const handleDuplicateGroup = () => {
    if (repeatable) {
      FormState.update((s) => {
        const currentRepeats = s.repeats || {};
        const groupRepeats = currentRepeats[id] || [0];
        const nextRepeatIndex = Math.max(...groupRepeats) + 1;
        s.repeats = {
          ...s.repeats,
          [id]: [...groupRepeats, nextRepeatIndex],
        };
      });
    }
  };

  return (
    <View>
      <View style={styles.fieldGroupHeader}>
        <Text style={styles.fieldGroupName} testID="text-name">
          {`${index + 1}. ${label}`}
        </Text>
        {repeatable && (
          <TouchableOpacity
            style={styles.fieldGroupCopy}
            testID="copy-button"
            onPress={handleDuplicateGroup}
          >
            <Icon type="ionicon" name="add-circle-outline" size={20} color={theme.icon.primary} testID="copy" />
          </TouchableOpacity>
        )}
      </View>
      <View style={styles.fieldGroupDescContainer}>
        {description && (
          <Text style={styles.fieldGroupDescription} testID="text-description">
            {description}
          </Text>
        )}
      </View>
    </View>
  );
};

export default FieldGroupHeader;
