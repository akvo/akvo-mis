import { renderHook, act } from '@testing-library/react-native';
import { Dimensions } from 'react-native';
import useDropdownPlacement from '../dropdown-placement';

const anchorAt = (y, height = 50) => ({
  current: { measureInWindow: (cb) => cb(0, y, 300, height) },
});

describe('useDropdownPlacement', () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, 'get').mockReturnValue({ width: 400, height: 800 });
  });

  it('opens a field near the bottom upward, capped to the room above', () => {
    const { result } = renderHook(() => useDropdownPlacement());
    act(() => result.current.place(anchorAt(650)));
    expect(result.current.placement).toEqual({ dropdownPosition: 'top', maxHeight: 500 });

    act(() => result.current.place(anchorAt(400)));
    // 400 - 48 above vs 800 - 450 - 48 below
    expect(result.current.placement).toEqual({ dropdownPosition: 'top', maxHeight: 352 });
  });

  it('opens a field near the top downward, capped to the room below', () => {
    const { result } = renderHook(() => useDropdownPlacement());
    act(() => result.current.place(anchorAt(300)));
    // 800 - 350 - 48 below
    expect(result.current.placement).toEqual({ dropdownPosition: 'bottom', maxHeight: 402 });
  });
});
