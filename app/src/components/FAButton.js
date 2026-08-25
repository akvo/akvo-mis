import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

/**
 * Floating Action Button component for use throughout the application
 * @param {Object} props - Component props
 * @param {string} props.label - Text to display on the button
 * @param {Function} props.onPress - Function to call when button is pressed
 * @param {string} [props.testID] - Test ID for the component
 * @param {number} [props.numberOfLines=2] - Maximum number of lines for the button text
 * @param {string} [props.backgroundColor='#1651b6'] - Button background color
 * @param {Object} [props.customStyle] - Custom styles to apply to the button
 * @param {Object} [props.customTextStyle] - Custom styles to apply to the button text
 * @param {Object} [props.icon] - Icon configuration object
 * @param {string} [props.icon.name] - Icon name from Ionicons
 * @param {number} [props.icon.size=18] - Icon size
 * @param {string} [props.icon.color='white'] - Icon color
 * @param {string} [props.iconPosition='left'] - Position of the icon ('left' or 'right')
 * @param {boolean} [props.disabled=false] - Whether the button is disabled
 */
const FAButton = ({
  label,
  onPress,
  testID = 'floating-action-button',
  numberOfLines = 2,
  backgroundColor = '#1651b6',
  customStyle = {},
  customTextStyle = {},
  icon = null,
  iconPosition = 'left',
  disabled = false,
}) => {
  // Absolutely positioned elements anchor to the screen edge, below the Android
  // navigation bar, so the inset has to be applied here rather than inherited from
  // the SafeAreaView this button is rendered inside.
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.buttonWrapper, { paddingBottom: insets.bottom }]}>
      <TouchableOpacity
        onPress={onPress}
        testID={testID}
        disabled={disabled}
        style={[
          styles.floatingButton,
          { backgroundColor: disabled ? '#cccccc' : backgroundColor },
          disabled && styles.disabledButton,
          customStyle,
        ]}
      >
        <View style={[styles.contentContainer, iconPosition === 'right' && styles.contentReverse]}>
          {icon?.name && iconPosition === 'left' && (
            <View style={styles.iconContainerLeft}>
              <Icon
                name={icon.name}
                size={icon?.size || 18}
                color={disabled ? '#999999' : icon?.color || 'white'}
              />
            </View>
          )}
          <Text
            style={[styles.floatingButtonText, disabled && styles.disabledText, customTextStyle]}
            numberOfLines={numberOfLines}
            ellipsizeMode="tail"
          >
            {label}
          </Text>
          {icon?.name && iconPosition === 'right' && (
            <View style={styles.iconContainerRight}>
              <Icon
                name={icon.name}
                size={icon?.size || 18}
                color={disabled ? '#999999' : icon?.color || 'white'}
              />
            </View>
          )}
        </View>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  buttonWrapper: {
    // 'fixed' is not a React Native position value — it fell back to in-flow
    // layout, so this wrapper occupied a full-width band at the bottom of the
    // screen and pushed list content behind it. 'absolute' floats it instead, and
    // box-none keeps taps passing through everywhere except the button itself.
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
    pointerEvents: 'box-none',
  },
  floatingButton: {
    borderRadius: 28,
    padding: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  floatingButtonText: {
    color: 'white',
    fontSize: 14,
    textAlign: 'center',
  },
  contentContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  contentReverse: {
    flexDirection: 'row-reverse',
  },
  iconContainerLeft: {
    marginRight: 8,
  },
  iconContainerRight: {
    marginLeft: 8,
  },
  disabledButton: {
    backgroundColor: '#cccccc',
  },
  disabledText: {
    color: '#999999',
  },
});

export default FAButton;
