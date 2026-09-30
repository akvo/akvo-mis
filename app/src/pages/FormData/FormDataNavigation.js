import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Button } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';
import { UIState } from '../../store';
import { i18n } from '../../lib';
import useTheme from '../../lib/theme';

const FormDataNavigation = ({ totalPage, currentPage, setCurrentPage }) => {
  const theme = useTheme();
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const goBack = () => {
    setCurrentPage(currentPage - 1);
  };
  const goNext = () => {
    setCurrentPage(currentPage + 1);
  };

  const disabledBack = currentPage === 0;
  const disabledNext = currentPage === totalPage - 1;
  const colorIconBack = disabledBack ? theme.text.tertiary : theme.text.primary;
  const colorIconNext = disabledNext ? theme.text.tertiary : theme.text.primary;
  return (
    <View style={[styles.container, { borderTopColor: theme.border.divider }]}>
      <Button
        type="clear"
        testID="button-back"
        disabled={disabledBack}
        onPress={goBack}
        icon={<Icon name="chevron-back" style={{ ...styles.icon, color: colorIconBack }} />}
        buttonStyle={styles.button}
        titleStyle={{ color: theme.text.primary }}
      >
        {trans.buttonBack}
      </Button>
      <Text testID="text-pagination" style={[styles.paginationText, { color: theme.text.primary }]}>
        {currentPage + 1}/{totalPage}
      </Text>
      <Button
        type="clear"
        testID="button-next"
        disabled={disabledNext}
        onPress={goNext}
        icon={<Icon name="chevron-forward" style={{ ...styles.icon, color: colorIconNext }} />}
        buttonStyle={styles.button}
        titleStyle={{ color: theme.text.primary }}
        iconRight
      >
        {trans.buttonNext}
      </Button>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    borderTopWidth: 0.5,
    borderBottomWidth: 0,
    paddingVertical: 8,
  },
  icon: {
    fontSize: 18,
    paddingHorizontal: 4,
  },
  button: {
    fontSize: 14,
    paddingHorizontal: 8,
  },
  paginationText: {
    width: '60%',
    textAlign: 'center',
    fontSize: 14,
  },
});

export default FormDataNavigation;
