import { useCallback, useEffect, useState } from 'react';
import { Dimensions, Keyboard } from 'react-native';

const MAX_HEIGHT = 500;
const MIN_HEIGHT = 160;
// Kept clear at the screen edges: the status bar above, Android's navigation bar below.
const EDGE = 48;

/**
 * Where a react-native-element-dropdown list opens, and how tall it may be.
 *
 * The library's 'auto' only flips upward when under 150px remain below the field, while the
 * list is allowed 500px — so a field in the lower half opened downward and ran under the
 * Android navigation bar, leaving the last options unreachable. This opens toward whichever
 * side has more room and caps the list to fit there.
 *
 * While the keyboard is up (typing in the list's search box) it hands back to 'auto': only
 * then does the library lift the list above the keyboard.
 *
 * Usage: wrap the dropdown in `<View ref={anchor} collapsable={false}>`, spread `placement`
 * onto it and pass `onFocus={() => place(anchor)}`.
 */
const useDropdownPlacement = () => {
  const [measured, setMeasured] = useState({ dropdownPosition: 'auto', maxHeight: MAX_HEIGHT });
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', (e) =>
      setKeyboardHeight(e.endCoordinates.height),
    );
    const hide = Keyboard.addListener('keyboardDidHide', () => setKeyboardHeight(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  const place = useCallback((anchorRef) => {
    anchorRef?.current?.measureInWindow((x, y, width, height) => {
      const { height: screenHeight } = Dimensions.get('window');
      const above = y - EDGE;
      const below = screenHeight - (y + height) - EDGE;
      const openUp = above > below;
      setMeasured({
        dropdownPosition: openUp ? 'top' : 'bottom',
        maxHeight: Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, openUp ? above : below)),
      });
    });
  }, []);

  if (keyboardHeight > 0) {
    const { height: screenHeight } = Dimensions.get('window');
    return {
      placement: {
        dropdownPosition: 'auto',
        maxHeight: Math.min(
          MAX_HEIGHT,
          Math.max(MIN_HEIGHT, screenHeight - keyboardHeight - EDGE * 2),
        ),
      },
      place,
    };
  }
  return { placement: measured, place };
};

export default useDropdownPlacement;
