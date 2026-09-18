import React, { useMemo } from 'react';
import { View } from 'react-native';
import { Text, Button } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';

import { FormState, BuildParamsState } from '../../store';
// Imported directly, not via '../support': that barrel re-exports FormNavigation, which
// pulls the lib barrel and with it expo-background-task - a native module a form field has
// no use for.
import FieldLabel from '../support/FieldLabel';
import { polygonAreaHectares } from '../lib/geometry';
import {
  areaIsAmbiguous,
  failedRules,
  formatRuleFailure,
  runPolygonRules,
} from '../lib/polygon-rules';
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
  extra = null,
}) => {
  const navigation = useNavigation();
  const activeLang = FormState.useState((s) => s.lang);
  const feedback = FormState.useState((s) => s.feedback?.[id]);
  const settings = BuildParamsState.useState((s) => s);
  const trans = i18n.text(activeLang);

  // Memoised so the empty-array fallback keeps its identity across renders: without this the
  // rule evaluation below re-runs on every render of an unanswered question.
  const points = useMemo(() => (Array.isArray(value) ? value : []), [value]);
  const requiredValue = required ? requiredSign : null;
  // A geotrace is an open line: it encloses nothing, so it has no area to report.
  const isClosed = type !== QUESTION_TYPES.geotrace;

  /**
   * Advisory only - no severity is presented here, the same way the web badge shows failures
   * without claiming they block anything (GEO-013 D-3). Whether a failure blocks is the submit
   * gate's question, and the gate answers it below the field.
   */
  const failures = useMemo(
    () => failedRules(runPolygonRules(points, { type, required, extra }, settings)),
    [points, type, required, extra, settings],
  );
  /**
   * Once the gate has spoken, the red message under the field owns the sentence; repeating it
   * in amber a few pixels above adds nothing. A warn never produces that message, so for a warn
   * this hint stays visible and remains its only channel. GEO-002 D-8.
   */
  const showHint = !feedback || feedback === true;
  // See GEO-003 D-6: an area computed over a self-crossing ring is not a measurement.
  const areaUnreliable = areaIsAmbiguous(failures);

  const handleDraw = () => {
    /**
     * `extra` travels with the route because MapDrawView runs the same rules as this field, and
     * one of them - the `maxAreaHa` ceiling - reads its threshold from the question rather than
     * from a constant (GEO-003 D-5). Without it the map silently evaluated every polygon as if
     * no ceiling were configured, which looks identical to "no ceiling set".
     */
    navigation.navigate('MapDrawView', { id, value: points, name: label, type, extra });
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
                <Text testID="text-area" style={areaUnreliable ? styles.polygonWarningText : null}>
                  {trans.polygonArea}: {areaUnreliable ? '~' : ''}
                  {polygonAreaHectares(points).toFixed(2)} ha
                </Text>
              )}
            </>
          ) : (
            <Text testID="text-no-points">{trans.polygonNoPoints}</Text>
          )}
          {showHint &&
            failures.map((failure) => (
              <Text
                key={failure.key}
                testID={`text-polygon-warning-${failure.key}`}
                style={styles.polygonWarningText}
              >
                {`\u26A0 ${formatRuleFailure(failure, trans)}`}
              </Text>
            ))}
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
