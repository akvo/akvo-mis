/* eslint-disable no-nested-ternary */
import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { Text, Button } from '@rneui/themed';
import Icon from 'react-native-vector-icons/Ionicons';

import { FormState, BuildParamsState, UserState } from '../../store';
import { FieldLabel } from '../support';
import { loc, i18n } from '../../lib';
import useTheme from '../../lib/theme';

const formatCoord = (val, isLat) => {
  if (val === null || val === undefined) {
    return '--';
  }
  const num = parseFloat(val);
  const abs = Math.abs(num).toFixed(4);
  if (isLat) {
    return `${abs}\u00B0 ${num >= 0 ? 'N' : 'S'}`;
  }
  return `${abs}\u00B0 ${num >= 0 ? 'E' : 'W'}`;
};

const TypeGeo = ({
  keyform,
  id,
  label,
  value = '',
  tooltip = null,
  required,
  requiredSign = '*',
  disabled = false,
}) => {
  const theme = useTheme();
  const [errorMsg, setErrorMsg] = useState(null);
  const [gpsAccuracy, setGpsAccuracy] = useState(null);
  const [loading, setLoading] = useState(false);
  const latitude = value?.[0] || null;
  const longitude = value?.[1] || null;

  const gpsAccuracyLevel = BuildParamsState.useState((s) => s.gpsAccuracyLevel);
  const geoLocationTimeout = BuildParamsState.useState((s) => s.geoLocationTimeout);
  const gpsThreshold = BuildParamsState.useState((s) => s.gpsThreshold);
  const activeLang = FormState.useState((s) => s.lang);
  const savedLocation = UserState.useState((s) => s.currentLocation);

  const trans = i18n.text(activeLang);

  const requiredValue = required ? requiredSign : null;

  const getCurrentLocation = async () => {
    await loc.getCurrentLocation(
      ({ coords }) => {
        const { latitude: lat, longitude: lng, accuracy } = coords;
        setGpsAccuracy(Math.floor(accuracy));

        FormState.update((s) => {
          s.currentValues = { ...s.currentValues, [id]: [lat, lng] };
        });
        setLoading(false);
      },
      ({ message }) => {
        setLoading(false);
        setErrorMsg(message);
        setGpsAccuracy(-1);

        FormState.update((s) => {
          s.currentValues = { ...s.currentValues, [id]: [-1.3855559, 37.9938594] };
        });
      },
      gpsAccuracyLevel,
    );
  };

  const handleGetCurrLocation = async () => {
    const geoTimeout = geoLocationTimeout * 1000;
    setLoading(true);
    setTimeout(() => {
      if (!value?.length && savedLocation?.coords) {
        const { latitude: lat, longitude: lng, accuracy } = savedLocation.coords;
        setGpsAccuracy(Math.floor(accuracy));
        FormState.update((s) => {
          s.currentValues = { ...s.currentValues, [id]: [lat, lng] };
        });
      }
      if (loading) {
        setLoading(false);
      }
    }, geoTimeout);
    await getCurrentLocation();
  };

  const hasLocation = latitude !== null;

  // Accuracy label and color
  let accuracyLabel = null;
  let accuracyColor = theme.text.tertiary;
  if (gpsAccuracy !== null) {
    if (gpsAccuracy < 0) {
      accuracyLabel = 'GPS Off';
      accuracyColor = theme.status.error;
    } else if (gpsAccuracy < 10) {
      accuracyLabel = 'High';
      accuracyColor = theme.status.success;
    } else if (gpsAccuracy < gpsThreshold) {
      accuracyLabel = 'Medium';
      accuracyColor = theme.status.warning;
    } else {
      accuracyLabel = 'Low';
      accuracyColor = theme.status.error;
    }
  }

  return (
    <View>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View style={[styles.card, { backgroundColor: theme.bg.surfaceElevated1 }]}>
        {/* Primary button */}
        <Button
          onPress={() => handleGetCurrLocation()}
          testID="button-curr-location"
          disabled={disabled || loading}
          loading={loading}
          buttonStyle={[styles.primaryButton, { backgroundColor: theme.buttonPrimary.bg }]}
          titleStyle={styles.primaryButtonTitle}
          containerStyle={styles.buttonContainer}
        >
          {loading ? trans.fetchingLocation : trans.buttonCurrLocation}
        </Button>

        {/* Refresh button (ghost) - only show after first location */}
        {hasLocation && !loading && (
          <Button
            type="clear"
            onPress={() => handleGetCurrLocation()}
            testID="button-refresh-location"
            disabled={disabled}
            titleStyle={[styles.ghostButtonTitle, { color: theme.buttonGhost.color }]}
            icon={
              <Icon
                name="refresh-outline"
                size={18}
                color={theme.buttonGhost.color}
                style={{ marginRight: 6 }}
              />
            }
          >
            {trans.buttonRefreshCurrLocation || 'Refresh location'}
          </Button>
        )}

        {/* Coordinate rows */}
        {hasLocation && (
          <View style={styles.coordSection}>
            <View style={styles.coordRow}>
              <Text style={[styles.coordLabel, { color: theme.text.primary }]}>
                {trans.latitude}
              </Text>
              <Text style={[styles.coordValue, { color: theme.text.primary }]}>
                {formatCoord(latitude, true)}
              </Text>
            </View>
            <View style={[styles.divider, { backgroundColor: theme.border.listDivider }]} />
            <View style={styles.coordRow}>
              <Text style={[styles.coordLabel, { color: theme.text.primary }]}>
                {trans.longitude}
              </Text>
              <Text style={[styles.coordValue, { color: theme.text.primary }]}>
                {formatCoord(longitude, false)}
              </Text>
            </View>

            {accuracyLabel && (
              <>
                <View style={[styles.divider, { backgroundColor: theme.border.listDivider }]} />
                <View style={styles.coordRow} testID="text-acc">
                  <Text style={[styles.coordLabel, { color: theme.text.primary }]}>
                    Accuracy level
                  </Text>
                  <View style={[styles.accuracyBadge, { backgroundColor: theme.bg.surfaceChip }]}>
                    <Icon name="cellular-outline" size={14} color={accuracyColor} />
                    <Text style={[styles.accuracyText, { color: theme.text.primary }]}>
                      {accuracyLabel}
                    </Text>
                  </View>
                </View>
              </>
            )}
          </View>
        )}

        {errorMsg && (
          <Text testID="text-error" style={[styles.errorText, { color: theme.status.error }]}>
            {errorMsg}
          </Text>
        )}
      </View>
    </View>
  );
};

export default TypeGeo;

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 10,
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  buttonContainer: {
    borderRadius: 24,
    overflow: 'hidden',
  },
  primaryButton: {
    borderRadius: 24,
    paddingVertical: 14,
  },
  primaryButtonTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  ghostButtonTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  coordSection: {
    marginTop: 4,
  },
  coordRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
  },
  coordLabel: {
    fontSize: 16,
    fontWeight: '400',
  },
  coordValue: {
    fontSize: 16,
    fontWeight: '400',
  },
  divider: {
    height: StyleSheet.hairlineWidth,
  },
  accuracyBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    gap: 4,
  },
  accuracyText: {
    fontSize: 14,
    fontWeight: '500',
  },
  errorText: {
    fontStyle: 'italic',
    fontSize: 13,
  },
});
