import React from 'react';
import { View, TouchableOpacity } from 'react-native';
import { Text, Icon, Divider } from '@rneui/themed';
import { FormState } from '../../store';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

const RepeatSection = ({ group, repeatIndex }) => {
  const theme = useTheme();
  const styles = getStyles(theme);

  // Skip rendering section title for the first instance (index 0)
  if (repeatIndex === 0) {
    return null;
  }

  const handleRemoveRepeat = () => {
    FormState.update((s) => {
      const currentRepeats = s.repeats || {};
      const groupRepeats = currentRepeats[group.id] || [0];
      const updatedRepeats = groupRepeats.filter((idx) => idx !== repeatIndex);
      s.repeats = {
        ...currentRepeats,
        [group.id]: updatedRepeats,
      };
    });
  };

  return (
    <View style={styles.repeatSectionContainer}>
      <Divider style={styles.repeatDivider} />
      <View style={styles.repeatSectionHeader}>
        <Text style={styles.repeatSectionTitle}>
          {`${group.label || group.name} #${repeatIndex + 1}`}
        </Text>
        <TouchableOpacity
          style={styles.repeatSectionRemove}
          onPress={handleRemoveRepeat}
          testID={`remove-repeat-${group.id}-${repeatIndex}`}
        >
          <Icon type="ionicon" name="trash-outline" size={20} color={theme.status.error} />
        </TouchableOpacity>
      </View>
    </View>
  );
};

export default RepeatSection;
