import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
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

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: theme.bg.surfaceElevated3, borderTopColor: theme.border.listDivider },
      ]}
    >
      <TouchableOpacity
        style={styles.backButton}
        onPress={goBack}
        disabled={disabledBack}
        testID="button-back"
      >
        <Text
          style={[
            styles.backText,
            { color: disabledBack ? theme.text.tertiary : theme.buttonGhost.color },
          ]}
        >
          {trans.buttonBack}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={[
          styles.nextButton,
          {
            backgroundColor: disabledNext
              ? theme.bg.surfaceTertiary
              : theme.buttonPrimary.bg,
          },
        ]}
        onPress={goNext}
        disabled={disabledNext}
        testID="button-next"
      >
        <Text
          style={[
            styles.nextText,
            { color: disabledNext ? theme.text.tertiary : theme.buttonPrimary.text },
          ]}
        >
          {trans.buttonNext}
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  backButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
  },
  backText: {
    fontSize: 18,
    fontWeight: '600',
  },
  nextButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 16,
  },
  nextText: {
    fontSize: 18,
    fontWeight: '600',
  },
});

export default FormDataNavigation;
