import React from 'react';
import { View } from 'react-native';
import { Text, Button } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';

import { FormState } from '../../store';
// Imported directly, not via '../support': that barrel re-exports FormNavigation, which
// pulls the lib barrel and with it expo-background-task - a native module a form field has
// no use for.
import FieldLabel from '../support/FieldLabel';
import { polygonAreaHectares } from '../lib/geometry';
import { QUESTION_TYPES } from '../../lib/constants';
import styles from '../styles';
import i18n from '../../lib/i18n';

const MIN_POINTS_FOR_AREA = 3;

/**
 * Summary only: the map itself lives on the MapDrawView screen, not here. A pan/zoom map
 * nested in the form's ScrollView makes every drag ambiguous. See GEO-001 D-5.
 */
const TypeGeoDrawing = ({
  keyform,
  id,
  label,
  type = QUESTION_TYPES.geoshape,
  value = [],
  tooltip = null,
  required,
  requiredSign = '*',
  disabled = false,
}) => {
  const navigation = useNavigation();
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const points = Array.isArray(value) ? value : [];
  const requiredValue = required ? requiredSign : null;
  // A geotrace is an open line: it encloses nothing, so it has no area to report.
  const isClosed = type !== QUESTION_TYPES.geotrace;

  const handleDraw = () => {
    navigation.navigate('MapDrawView', { id, value: points, name: label, type });
  };

  return (
    <View>
      <FieldLabel keyform={keyform} name={label} tooltip={tooltip} requiredSign={requiredValue} />
      <View style={styles.inputGeoContainer}>
        <View>
          {points.length ? (
            <>
              <Text testID="text-point-count">
                {trans.polygonPoints}: {points.length}
              </Text>
              {isClosed && points.length >= MIN_POINTS_FOR_AREA && (
                <Text testID="text-area">
                  {trans.polygonArea}: {polygonAreaHectares(points).toFixed(2)} ha
                </Text>
              )}
            </>
          ) : (
            <Text testID="text-no-points">{trans.polygonNoPoints}</Text>
          )}
        </View>
        <View style={styles.geoButtonGroup}>
          <Button onPress={handleDraw} testID="button-draw-on-map" disabled={disabled}>
            {trans.buttonDrawOnMap}
          </Button>
        </View>
      </View>
    </View>
  );
};

export default TypeGeoDrawing;
