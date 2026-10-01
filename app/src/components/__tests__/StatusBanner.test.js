import React from 'react';
import { render, act } from '@testing-library/react-native';
import { UIState } from '../../store';
import StatusBanner, { resolveBanner } from '../StatusBanner';
import { getTheme } from '../../lib/theme';
import { SYNC_STATUS } from '../../lib/constants';

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

describe('resolveBanner precedence', () => {
  const theme = getTheme(false);
  const trans = {
    offlineText: 'offline',
    lowStorageText: 'low storage',
    doneText: 'done',
    syncErrorText: 'sync error',
    syncRejectedText: 'sync rejected',
  };
  const statusText = {
    [SYNC_STATUS.on_progress]: 'syncing',
    [SYNC_STATUS.failed]: 'failed',
    [SYNC_STATUS.rejected]: 'rejected',
  };
  const pick = (overrides) =>
    resolveBanner({
      syncType: null,
      isOnline: true,
      lowStorage: false,
      statusText,
      theme,
      trans,
      ...overrides,
    });

  it('sync activity outranks low storage', () => {
    expect(pick({ syncType: SYNC_STATUS.on_progress, lowStorage: true }).text).toBe('syncing');
  });

  it('low storage outranks a failed or rejected sync', () => {
    expect(pick({ syncType: SYNC_STATUS.rejected, lowStorage: true }).isLowStorage).toBe(true);
    expect(pick({ syncType: SYNC_STATUS.failed, lowStorage: true }).isLowStorage).toBe(true);
  });

  it('a failed sync shows when storage is fine', () => {
    expect(pick({ syncType: SYNC_STATUS.failed })).toMatchObject({
      text: 'failed',
      bg: theme.status.error,
    });
  });

  it('falls back to plain status text when statusText is missing', () => {
    expect(pick({ syncType: SYNC_STATUS.failed, statusText: null }).text).toBe('sync error');
    expect(pick({ syncType: SYNC_STATUS.rejected, statusText: undefined }).text).toBe(
      'sync rejected',
    );
    // An entry missing from a present statusText falls back too, instead of reading "offline".
    expect(pick({ syncType: SYNC_STATUS.success }).text).toBe('done');
  });

  it('a stale sync status cannot mask offline', () => {
    expect(pick({ isOnline: false, syncType: SYNC_STATUS.on_progress }).text).toBe('offline');
    expect(pick({ isOnline: false, syncType: SYNC_STATUS.failed }).text).toBe('offline');
    // Low storage still outranks offline, stale sync status or not.
    expect(
      pick({ isOnline: false, syncType: SYNC_STATUS.success, lowStorage: true }).isLowStorage,
    ).toBe(true);
  });

  it('offline shows only when nothing else applies', () => {
    expect(pick({ isOnline: false }).text).toBe('offline');
    expect(pick({ isOnline: false, lowStorage: true }).isLowStorage).toBe(true);
  });

  it('online with nothing to report shows no banner', () => {
    expect(pick({})).toBeNull();
  });
});

describe('resolveBanner contrast', () => {
  // WCAG relative luminance / contrast ratio, enough to guard the banner tokens.
  const luminance = (hex) => {
    const [r, g, b] = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a, b) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  const cases = [
    { syncType: SYNC_STATUS.on_progress },
    { syncType: SYNC_STATUS.success },
    { lowStorage: true },
    { syncType: SYNC_STATUS.failed },
    { isOnline: false },
  ];

  [true, false].forEach((isDark) => {
    const theme = getTheme(isDark);
    cases.forEach((overrides) => {
      it(`${isDark ? 'dark' : 'light'} ${JSON.stringify(overrides)} meets AA 4.5:1`, () => {
        const banner = resolveBanner({
          syncType: null,
          isOnline: true,
          lowStorage: false,
          statusText: {},
          theme,
          trans: {},
          ...overrides,
        });
        expect(contrast(banner.bg, banner.color)).toBeGreaterThanOrEqual(4.5);
      });
    });
  });
});
