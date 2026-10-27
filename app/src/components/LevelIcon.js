import React from 'react';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import useTheme from '../lib/theme';

// Every level option shares one graded icon: 1, 2 or 3 bars (APP-487 A8).
const TIERS = {
  accuracy: { 1: 1, 2: 1, 3: 2, 4: 3, 5: 3 },
  imageQuality: { low: 1, medium: 2, high: 3, original: 3 },
};

export const getLevelTier = (kind, level) => TIERS[kind]?.[level] || null;

const LevelIcon = ({ kind, level, size = 14 }) => {
  const theme = useTheme();
  const tier = getLevelTier(kind, level);
  if (!tier) {
    return null;
  }
  return (
    <Icon
      name={`signal-cellular-${tier}`}
      size={size}
      color={theme.status.success}
      testID={`level-icon-${tier}`}
    />
  );
};

export default LevelIcon;
