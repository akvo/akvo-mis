/**
 * Centralized theme system with design tokens from Figma.
 *
 * Two palettes (dark / light) share the same semantic keys so every component
 * can reference `theme.bg.surfacePrimary` etc. without caring which mode is
 * active.  The active palette is stored in UIState.isDarkMode and consumed via
 * the `useTheme` hook.
 */

import { Appearance, useColorScheme } from 'react-native';
import { UIState } from '../store';

// ---------------------------------------------------------------------------
// Color palettes – extracted from the Figma design-token JSON exports
// (Dark.tokens.json / Light.tokens.json, Sep 2026).
// ---------------------------------------------------------------------------

const dark = {
  // ---- backgrounds ----
  bg: {
    surfacePrimary: '#000000',
    surfaceSecondary: '#141414',
    surfaceTertiary: '#1B1B1B',
    surfaceElevated1: '#141414',
    surfaceElevated2: '#1F1F1F',
    surfaceElevated3: '#242424',
    surfaceTranslucent: 'rgba(255,255,255,0.11)',
    scrim: 'rgba(0,0,0,0.35)',
    surfaceChip: '#333333',
  },

  // ---- text ----
  text: {
    primary: '#FFFFFF',
    secondary: '#AFAFAF',
    tertiary: '#757575',
    highlight: '#365DFF',
  },

  // ---- icons ----
  icon: {
    primary: '#FFFFFF',
    secondary: '#808080',
    accent: '#8CA2FF',
  },

  // ---- buttons – primary ----
  buttonPrimary: {
    bg: '#0434FF',
    bgHover: '#365DFF',
    bgPressed: '#5777FF',
    bgDisabled: '#334155',
    text: '#FFFFFF',
    textDisabled: '#1E293B',
  },

  // ---- buttons – secondary ----
  buttonSecondary: {
    bg: '#8CA2FF',
    bgHover: '#5777FF',
    bgPressed: '#5777FF',
    bgDisabled: '#334155',
    text: '#0434FF',
    textDisabled: '#CBD5E1',
  },

  // ---- buttons – tertiary ----
  buttonTertiary: {
    bg: '#FFFFFF',
    bgHover: '#1E293B',
    bgPressed: '#1E293B',
    border: '#475569',
    borderDisabled: '#475569',
    text: '#FFFFFF',
    textDisabled: '#475569',
  },

  // ---- buttons – ghost ----
  buttonGhost: {
    color: '#5777FF',
    colorHover: '#042FE8',
    colorPressed: '#0325B5',
    colorDisabled: '#8CA2FF',
  },

  // ---- status ----
  status: {
    success: '#00DD00',
    warning: '#FF920A',
    draft: '#FFE50D',
    error: '#FF2C20',
  },

  // ---- borders ----
  border: {
    divider: '#333333',
    subtle: '#1F1F1F',
    listDivider: '#383838',
  },

  // ---- notification badge ----
  badge: {
    bg: '#FF6C64',
    text: '#FFFFFF',
    border: '#000000',
  },

  // ---- bottom navigation ----
  bottomNav: {
    bg: '#000000',
    border: '#1E293B',
    selected: '#FFFFFF',
    deselected: '#475569',
    indicator: '#FFFFFF',
  },

  // ---- top navigation ----
  topNav: {
    bg: '#000000',
    text: '#FFFFFF',
    icon: '#FFFFFF',
    modal: '#000000',
    modal2: '#333333',
  },

  // ---- text fields ----
  input: {
    bg: '#252525',
    border: '#475569',
    borderHover: '#CBD5E1',
    borderPressed: '#94A3B8',
    text: '#CBD5E1',
    textInput: '#FFFFFF',
    searchBg: '#334155',
    searchBgHover: '#475569',
    searchBgPressed: '#475569',
    searchText: '#94A3B8',
    errorBorder: '#FF2C20',
    errorText: '#FF2C20',
    errorInput: '#FFFFFF',
    successBorder: '#00B505',
    successText: '#00B505',
    successInput: '#FFFFFF',
    disabledText: '#475569',
    disabledIcon: '#FFD600',
  },

  // ---- system bars ----
  statusBar: {
    text: '#FFFFFF',
    bg: '#000000',
    style: 'light',
  },
};

const light = {
  // ---- backgrounds ----
  bg: {
    surfacePrimary: '#EEEEEE',
    surfaceSecondary: '#FFFFFF',
    surfaceTertiary: '#EAEAEA',
    surfaceElevated1: '#FFFFFF',
    surfaceElevated2: '#FFFFFF',
    surfaceElevated3: '#FFFFFF',
    surfaceTranslucent: 'rgba(0,0,0,0.06)',
    scrim: 'rgba(0,0,0,0.35)',
    surfaceChip: '#E2E2E2',
  },

  // ---- text ----
  text: {
    primary: '#141414',
    secondary: '#333333',
    tertiary: '#545454',
    highlight: '#0434FF',
  },

  // ---- icons ----
  icon: {
    primary: '#141414',
    secondary: '#545454',
    accent: '#0434FF',
  },

  // ---- buttons – primary ----
  buttonPrimary: {
    bg: '#0434FF',
    bgHover: '#042FE8',
    bgPressed: '#0325B5',
    bgDisabled: '#F1F5F9',
    text: '#FFFFFF',
    textDisabled: '#CBD5E1',
  },

  // ---- buttons – secondary ----
  buttonSecondary: {
    bg: '#B1C0FF',
    bgHover: '#8CA2FF',
    bgPressed: '#8CA2FF',
    bgDisabled: '#F1F5F9',
    text: '#0325B5',
    textDisabled: '#CBD5E1',
  },

  // ---- buttons – tertiary ----
  buttonTertiary: {
    bg: '#FFFFFF',
    bgHover: '#F8FAFC',
    bgPressed: '#F1F5F9',
    border: '#64748B',
    borderDisabled: '#E2E8F0',
    text: '#020617',
    textDisabled: '#CBD5E1',
  },

  // ---- buttons – ghost ----
  buttonGhost: {
    color: '#0434FF',
    colorHover: '#042FE8',
    colorPressed: '#0325B5',
    colorDisabled: '#8CA2FF',
  },

  // ---- status ----
  status: {
    success: '#086C0C',
    warning: '#A1440B',
    draft: '#89570A',
    error: '#C8170D',
  },

  // ---- borders ----
  border: {
    divider: '#AFAFAF',
    subtle: '#AFAFAF',
    listDivider: '#E2E2E2',
  },

  // ---- notification badge ----
  badge: {
    bg: '#FF2C20',
    text: '#FFFFFF',
    border: '#FFFFFF',
  },

  // ---- bottom navigation ----
  bottomNav: {
    bg: '#EAEAEA',
    border: '#94A3B8',
    selected: '#020617',
    deselected: '#475569',
    indicator: '#000000',
  },

  // ---- top navigation ----
  topNav: {
    bg: '#EAEAEA',
    text: '#020617',
    icon: '#020617',
    modal: '#000000',
    modal2: '#D9D9D9',
  },

  // ---- text fields ----
  input: {
    bg: '#FFFFFF',
    border: '#64748B',
    borderHover: '#CBD5E1',
    borderPressed: '#94A3B8',
    text: '#475569',
    textInput: '#020617',
    searchBg: '#F8FAFC',
    searchBgHover: '#F1F5F9',
    searchBgPressed: '#F1F5F9',
    searchText: '#475569',
    errorBorder: '#C8170D',
    errorText: '#C8170D',
    errorInput: '#020617',
    successBorder: '#086C0C',
    successText: '#086C0C',
    successInput: '#020617',
    disabledText: '#CBD5E1',
    disabledIcon: '#FFD600',
  },

  // ---- system bars ----
  statusBar: {
    text: '#000000',
    bg: '#FFFFFF',
    style: 'dark',
  },
};

// ---------------------------------------------------------------------------
// Typography scale – Inter font, sizes from the Figma typography page.
// Weights: 300 (light), 400 (regular), 500 (medium), 700 (bold).
// ---------------------------------------------------------------------------

const typography = {
  fontFamily: 'Inter',
  size: {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 18,
    xl: 20,
    xxl: 24,
    xxxl: 28,
    display: 35,
  },
  lineHeight: {
    xs: 16,
    sm: 20,
    md: 24,
    lg: 26,
    xl: 28,
    xxl: 30,
    xxxl: 36,
    display: 40,
  },
  weight: {
    light: '300',
    regular: '400',
    medium: '500',
    bold: '700',
  },
};

// ---------------------------------------------------------------------------
// Spacing scale (4-pt grid).
// ---------------------------------------------------------------------------

const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  xxxxl: 48,
};

// ---------------------------------------------------------------------------
// Border radii.
// ---------------------------------------------------------------------------

const radius = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Return the full palette object for the given mode. */
const getTheme = (isDark = false) => {
  const palette = isDark ? dark : light;
  return {
    ...palette,
    typography,
    spacing,
    radius,
    isDark,
  };
};

/**
 * React hook – returns the current theme palette based on UIState.isDarkMode.
 *
 * Components that call this hook will re-render when isDarkMode changes.
 */
const useTheme = () => {
  const preference = UIState.useState((s) => s.darkModePreference) || 'auto';
  const hookScheme = useColorScheme();
  // Fallback to Appearance API if hook returns null (Genymotion/emulator issue)
  const systemScheme = hookScheme || Appearance.getColorScheme();
  let isDark;
  if (preference === 'auto') {
    isDark = systemScheme === 'dark';
  } else {
    isDark = preference === 'dark';
  }
  return getTheme(isDark);
};

export { dark, light, typography, spacing, radius, getTheme };
export default useTheme;
