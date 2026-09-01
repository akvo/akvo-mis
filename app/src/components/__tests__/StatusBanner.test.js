import React from 'react';
import { render, act } from '@testing-library/react-native';
import { UIState } from '../../store';
import StatusBanner from '../StatusBanner';

describe('StatusBanner', () => {
  it('should render correctly when offline', () => {
    const { getByTestId } = render(<StatusBanner />);
    const textEl = getByTestId('offline-text');
    expect(textEl).toBeDefined();
    expect(textEl.props.children).toBe("You're offline...");
  });

  it('should render null when online', () => {
    const { queryByTestId } = render(<StatusBanner />);
    act(() => {
      UIState.update((s) => {
        s.online = true;
      });
    });
    const textEl = queryByTestId('offline-text');
    expect(textEl).toBeNull();
  });
});
