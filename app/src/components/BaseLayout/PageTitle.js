import React from 'react';
import Icon from 'react-native-vector-icons/Ionicons';
import { View, StyleSheet } from 'react-native';
import { Header, Text, Button } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';
import useTheme from '../../lib/theme';

const BackButton = ({ navigation, theme }) => {
  const handleGoBackPress = () => {
    navigation.goBack();
  };

  return navigation.canGoBack() ? (
    <Button type="clear" onPress={handleGoBackPress} testID="arrow-back-button">
      <Icon name="arrow-back" size={18} color={theme.topNav.icon} />
    </Button>
  ) : (
    <Text />
  );
};

const PageTitle = ({
  text,
  subTitle = null,
  leftComponent = null,
  leftContainerStyle = null,
  rightComponent = null,
  rightContainerStyle = null,
  headerBg = null,
}) => {
  const navigation = useNavigation();
  const theme = useTheme();

  const handleSettingsPress = () => {
    navigation.navigate('Home', { screen: 'SettingsTab' });
  };

  const hasBackButton = !leftComponent && navigation.canGoBack();

  return (
    <Header
      leftComponent={leftComponent}
      leftContainerStyle={[styles.sideContainer, leftContainerStyle]}
      rightComponent={rightComponent}
      rightContainerStyle={[styles.sideContainer, styles.sideContainerRight, rightContainerStyle]}
      centerContainerStyle={styles.centerContainer}
      backgroundColor={headerBg || theme.topNav.bg}
      statusBarProps={{
        backgroundColor: theme.statusBar.bg,
        barStyle: theme.statusBar.style === 'light' ? 'light-content' : 'dark-content',
      }}
      containerStyle={styles.container}
      testID="base-layout-page-title"
    >
      {!leftComponent && <BackButton navigation={navigation} theme={theme} />}
      {subTitle ? (
        <View>
          <Text
            h4Style={[
              styles.title,
              { color: theme.topNav.text },
              !hasBackButton && styles.titleLeft,
            ]}
            testID="page-title"
            numberOfLines={1}
            h4
          >
            {text}
          </Text>
          <Text
            testID="page-subtitle"
            style={[
              styles.subTitle,
              { color: theme.topNav.textSecondary || theme.text.secondary },
              !hasBackButton && styles.subTitleLeft,
            ]}
            numberOfLines={1}
          >
            {subTitle}
          </Text>
        </View>
      ) : (
        <Text
          h4Style={[
            styles.onlyTitle,
            { color: theme.topNav.text },
            !hasBackButton && styles.titleLeft,
          ]}
          testID="page-title"
          h4
        >
          {text}
        </Text>
      )}
      {rightComponent === null && (
        <Button type="clear" testID="more-options-button" onPress={handleSettingsPress}>
          <Icon name="ellipsis-vertical" size={18} color={theme.topNav.icon} />
        </Button>
      )}
    </Header>
  );
};

const styles = StyleSheet.create({
  container: {
    minHeight: 78,
    alignItems: 'center',
    borderBottomWidth: 0,
  },
  centerContainer: {
    flex: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sideContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  sideContainerRight: {
    alignItems: 'flex-end',
  },
  title: {
    fontSize: 18,
    textAlign: 'center',
  },
  titleLeft: {
    textAlign: 'left',
  },
  onlyTitle: {
    fontSize: 18,
    textAlign: 'center',
  },
  subTitle: {
    fontWeight: '400',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 2,
  },
  subTitleLeft: {
    textAlign: 'left',
  },
});

export default PageTitle;
