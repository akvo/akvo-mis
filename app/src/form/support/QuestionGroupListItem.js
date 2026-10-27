import React from 'react';
import { TouchableOpacity } from 'react-native';
import { Text, Icon } from '@rneui/themed';
import getStyles from '../styles';
import useTheme from '../../lib/theme';

const QuestionGroupListItem = ({
  label,
  active,
  completedQuestionGroup,
  hasErrors,
  visited,
  onPress,
}) => {
  const theme = useTheme();
  const styles = getStyles(theme);

  // Determine icon and color based on state
  let iconName = 'circle';
  let iconType = 'font-awesome';
  let bgColor = theme.text.tertiary;

  if (completedQuestionGroup) {
    iconName = 'check-circle';
    iconType = 'font-awesome';
    bgColor = theme.status.success;
  } else if (visited && hasErrors) {
    iconName = 'alert-circle-outline';
    iconType = 'ionicon';
    bgColor = theme.status.warning;
  } else if (visited) {
    iconName = 'circle';
    iconType = 'font-awesome';
    bgColor = theme.text.highlight;
  }

  const activeOpacity = active ? styles.questionGroupListItemActive : {};
  const activeName = active ? styles.questionGroupListItemNameActive : {};

  return (
    <TouchableOpacity
      style={{ ...styles.questionGroupListItemWrapper, ...activeOpacity }}
      testID="question-group-list-item-wrapper"
      onPress={onPress}
    >
      <Icon
        testID="icon-mark"
        name={iconName}
        type={iconType}
        color={bgColor}
        style={styles.questionGroupListItemIcon}
      />
      <Text style={{ ...styles.questionGroupListItemName, ...activeName }}>{label}</Text>
    </TouchableOpacity>
  );
};

export default QuestionGroupListItem;
