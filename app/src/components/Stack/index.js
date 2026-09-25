import React from 'react';
import { View } from 'react-native';
import styles from './styles';
import useTheme from '../../lib/theme';

const Stack = ({
  children = null,
  columns = 1,
  row = false,
  reverse = false,
  background = null,
  gap = 8,
}) => {
  const theme = useTheme();
  const bgColor = background || theme.bg.surfacePrimary;
  let flexDir = row ? 'row' : 'column';
  flexDir += reverse ? '-reverse' : '';

  // Calculate width accounting for gaps between items
  const gapTotal = (gap * (columns - 1)) / columns;
  const itemWidth = `${100 / columns - gapTotal}%`;

  return (
    <View
      style={{
        ...styles.container,
        flexDirection: flexDir,
        backgroundColor: bgColor,
      }}
      testID="stack-container"
    >
      {React.Children.map(children, (child, index) => {
        if (child) {
          return React.cloneElement(child, {
            style: {
              ...child?.props?.style,
              width: itemWidth,
              marginRight: (index + 1) % columns !== 0 ? gap : 0,
              marginBottom: gap,
            },
          });
        }
        return null;
      })}
    </View>
  );
};

export default Stack;
