import React from 'react';
import { SearchBar } from '@rneui/themed';
import { SafeAreaView } from 'react-native-safe-area-context';
import PageTitle from './PageTitle';
import Content from './Content';
import { UIState } from '../../store';
import useTheme from '../../lib/theme';

const BaseLayout = ({
  children,
  title = null,
  subTitle = null,
  search = { placeholder: null, show: false, value: null, action: null },
  leftComponent = null,
  leftContainerStyle = {},
  rightComponent = null,
  rightContainerStyle = {},
}) => {
  const isOnline = UIState.useState((s) => s.online);
  const statusBar = UIState.useState((s) => s.statusBar);
  const theme = useTheme();
  const networkBarVisible = !isOnline || statusBar !== null;
  const edges = networkBarVisible ? ['left', 'right'] : ['left', 'right', 'bottom'];

  return (
    <SafeAreaView
      style={{
        flex: 1,
        backgroundColor: theme.bg.surfacePrimary,
      }}
      edges={edges}
    >
      {title && (
        <PageTitle
          text={title}
          subTitle={subTitle}
          {...{ leftComponent, leftContainerStyle, rightComponent, rightContainerStyle }}
        />
      )}
      {search.show && (
        <SearchBar
          placeholder={search.placeholder}
          value={search.value}
          onChangeText={search.action}
          testID="search-bar"
          containerStyle={{
            width: '100%',
            backgroundColor: theme.topNav.bg,
            borderTopWidth: 0,
            borderBottomWidth: 0,
          }}
          inputContainerStyle={{
            backgroundColor: theme.input.bg,
            borderRadius: 12,
          }}
          inputStyle={{
            color: theme.input.textInput,
            fontSize: 16,
          }}
          searchIcon={{ size: 20, color: theme.icon.secondary }}
          clearIcon={{ size: 20, color: theme.icon.secondary }}
          placeholderTextColor={theme.input.text}
        />
      )}
      {children}
    </SafeAreaView>
  );
};

BaseLayout.Content = Content;

export default BaseLayout;
