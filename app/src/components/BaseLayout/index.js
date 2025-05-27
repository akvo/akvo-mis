import React from 'react';
import { SearchBar } from '@rneui/themed';
import { SafeAreaView } from 'react-native-safe-area-context';
import PageTitle from './PageTitle';
import Content from './Content';

const BaseLayout = ({
  children,
  title = null,
  subTitle = null,
  search = { placeholder: null, show: false, value: null, action: null },
  leftComponent = null,
  leftContainerStyle = {},
  rightComponent = null,
  rightContainerStyle = {},
}) => (
  <SafeAreaView
    style={{
      flex: 1,
      flexWrap: 'wrap',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      backgroundColor: '#f9fafb',
    }}
    edges={['bottom', 'left', 'right']}
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
        containerStyle={{ width: '100%' }}
      />
    )}
    {children}
  </SafeAreaView>
);

BaseLayout.Content = Content;

export default BaseLayout;
