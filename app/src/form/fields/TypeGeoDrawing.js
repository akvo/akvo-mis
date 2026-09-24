import React, { useCallback, useMemo, useState } from 'react';
import { View } from 'react-native';
import { Text, Button } from '@rneui/themed';
import { useNavigation } from '@react-navigation/native';
import * as SQLite from 'expo-sqlite';
import * as Sentry from '@sentry/react-native';

import { FormState, UserState } from '../../store';
import FieldLabel from '../support/FieldLabel';
import { polygonAreaHectares } from '../lib/geometry';
import {
  SEVERITY,
  areaIsAmbiguous,
  failedRules,
  formatRuleFailure,
  hasConfiguredRules,
  runPolygonRules,
} from '../lib/polygon-rules';
import { detectOverlapsEnabled, signatureOf } from '../lib/overlap';
import { accuracyThreshold as resolveAccuracyThreshold } from '../lib/gps-vertex';
import {
  OVERLAP_STATUS,
  conflictsForMap,
  notValidatedResult,
  overlapResults,
  runOverlapCheck,
} from '../lib/overlap-check';
import { requestDatapointSync } from '../../lib/sync-datapoints';
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
  const db = SQLite.useSQLiteContext();
  const activeLang = FormState.useState((s) => s.lang);
  const feedback = FormState.useState((s) => s.feedback?.[id]);
  const stored = FormState.useState((s) => s.polygonValidation?.[id]);
  const submissionUuid = FormState.useState((s) => s.submissionUuid);
  const overlapFormId = FormState.useState((s) => s.overlapFormId);
  const userId = UserState.useState((s) => s.id);
  const [checking, setChecking] = useState(false);
  const trans = i18n.text(activeLang);

  const points = useMemo(() => (Array.isArray(value) ? value : []), [value]);
  const requiredValue = required ? requiredSign : null;
  const isClosed = type !== QUESTION_TYPES.geotrace;
  const question = useMemo(
    () => ({ id, type, required, extra, label }),
    [id, type, required, extra, label],
  );

  /**
   * Advisory only - no severity is presented here, the same way the web badge shows failures
   * without claiming they block anything (GEO-013 D-3). Whether a failure blocks is the submit
   * gate's question, and the gate answers it below the field.
   */
  const failures = useMemo(
    () => failedRules(runPolygonRules(points, { type, required, extra })),
    [points, type, required, extra],
  );
  /**
   * Once the gate has spoken, the red message under the field owns the sentence; repeating it
   * in amber a few pixels above adds nothing. A warn never produces that message, so for a warn
   * this hint stays visible and remains its only channel. GEO-002 D-8.
   */
  const showHint = !feedback || feedback === true;
  const areaUnreliable = areaIsAmbiguous(failures);

  /**
   * A verdict belongs to the geometry it was computed from. Editing the polygon after a pass
   * returns the field to "not validated" rather than leaving a stale green tick (GEO-007 D-1),
   * and the submit gate applies the same comparison so an edit cannot slip past it.
   */
  const isStale = !stored || stored.signature !== signatureOf(points);
  const status = isStale ? OVERLAP_STATUS.notValidated : stored.status;

  /** No configured rules means no Validate button at all - a plain geoshape looks like phase 1. */
  const showValidate = hasConfiguredRules({ extra }) && points.length > 0;

  /**
   * The report replaces the amber hints once it exists: re-validating after a fix must replace
   * the previous report rather than leave two lists of the same failures on screen.
   *
   * And once the gate has spoken, the blocking lines drop out of the report for the same reason
   * `showHint` drops the amber ones - the gate renders the identical sentence a few pixels
   * below, prefixed with the question label, so keeping both printed the overlap twice on
   * device. Warnings stay: a warn never reaches the gate, so this is its only channel
   * (GEO-002 D-8).
   */
  const reportFailures = useMemo(() => {
    if (status === OVERLAP_STATUS.notValidated || status === OVERLAP_STATUS.checking) {
      return [];
    }
    const all = [...failures, ...(stored?.results || [])];
    if (showHint) {
      return all;
    }
    return all.filter((failure) => failure.severity !== SEVERITY.block);
  }, [status, failures, stored, showHint]);

  /**
   * "Not checked yet" needs a channel of its own.
   *
   * For a REQUIRED question the submit gate eventually says it, but only once the enumerator
   * tries to submit. For an OPTIONAL one it is never said at all: the result resolves to `warn`
   * (D-7), and `blockingMessage` keeps only `block`. The acceptance table has always promised
   * "Not required / Not validated -> warn only", and that row was simply not implemented.
   *
   * Shown as an amber hint beside the Validate button, on the same `showHint` rule as the other
   * advisory lines, so it never duplicates a sentence the gate is already printing.
   */
  const pendingNotice = useMemo(() => {
    if (!showValidate || status !== OVERLAP_STATUS.notValidated || !showHint) {
      return null;
    }
    return formatRuleFailure(notValidatedResult(question), trans);
  }, [showValidate, status, showHint, question, trans]);

  const handleValidate = useCallback(async () => {
    setChecking(true);
    const signature = signatureOf(points);
    try {
      const result = detectOverlapsEnabled({ extra })
        ? await runOverlapCheck(db, {
            points,
            question,
            formId: overlapFormId,
            excludeUuid: submissionUuid,
          })
        : { status: OVERLAP_STATUS.passed, conflicts: [] };
      const results = overlapResults(result, question);
      /**
       * The shape rules already ran synchronously above; their failures are merged into the
       * report at render. Only the overlap verdict is stored, because only it is expensive
       * enough that the submit gate must not re-run it.
       */
      const blockedByShape = failures.length > 0;
      const verdict =
        result.status === OVERLAP_STATUS.passed && blockedByShape
          ? OVERLAP_STATUS.failed
          : result.status;
      FormState.update((s) => {
        s.polygonValidation = {
          ...s.polygonValidation,
          [id]: {
            status: verdict,
            results,
            cause: result.cause || null,
            retryable: Boolean(result.retryable),
            /**
             * Kept, worst-first order and all, because the review screen draws from this array
             * and must never re-run the check to fetch it: a second run could sort differently,
             * and then `#1` on the map would not be `#1` in the sentence above (GEO-007 D-11).
             */
            conflicts: result.conflicts || [],
            signature,
            at: new Date().toISOString(),
          },
        };
      });
    } catch (error) {
      /**
       * An unexpected throw must not read as a pass. It is recorded as unavailable with no
       * Retry, which blocks a required question exactly as a failure does (D-10).
       */
      Sentry.captureException(error);
      FormState.update((s) => {
        s.polygonValidation = {
          ...s.polygonValidation,
          [id]: {
            status: OVERLAP_STATUS.unavailable,
            results: overlapResults(
              { status: OVERLAP_STATUS.unavailable, cause: 'localFailure' },
              question,
            ),
            cause: 'localFailure',
            retryable: false,
            conflicts: [],
            signature,
            at: new Date().toISOString(),
          },
        };
      });
    } finally {
      setChecking(false);
    }
  }, [db, points, question, extra, overlapFormId, submissionUuid, failures, id]);

  const handleRetrySync = useCallback(async () => {
    try {
      await requestDatapointSync(db, userId);
    } catch (error) {
      Sentry.captureException(error);
    }
    /**
     * Sync is asynchronous and may take minutes. The enumerator presses Validate again when it
     * finishes - Retry never auto-passes the question (D-10).
     */
    FormState.update((s) => {
      s.polygonValidation = { ...s.polygonValidation, [id]: null };
    });
  }, [db, userId, id]);

  const handleDraw = () => {
    /**
     * `extra` travels with the route because MapDrawView runs the same rules as this field, and
     * one of them - the `maxAreaHa` ceiling - reads its threshold from the question rather than
     * from a constant (GEO-003 D-5). Without it the map silently evaluated every polygon as if
     * no ceiling were configured, which looks identical to "no ceiling set".
     */
    navigation.navigate('MapDrawView', { id, value: points, name: label, type, extra });
  };

  /**
   * Offered only while the stored verdict still describes the polygon on screen: `status` is
   * already `notValidated` once the signature stops matching, so an edit withdraws the button
   * rather than opening a map of a shape that no longer exists.
   */
  const conflicts = stored?.conflicts || [];
  const showReviewMap = status === OVERLAP_STATUS.failed && conflicts.length > 0;

  const handleReviewOverlaps = () => {
    navigation.navigate('OverlapMapView', {
      value: points,
      /**
       * Labelled here, at the source, rather than by the screen. `conflictsForMap` and the
       * message's `conflictList` share one numbering function, so labelling anywhere else is a
       * chance to drift — and the screen then needs no import of the check that produced this.
       */
      conflicts: conflictsForMap(conflicts),
      name: label,
      type,
      /**
       * The question's own threshold, so the review screen marks a neighbour's loose corner
       * against the same number the capture screen used (GEO-008 D-4). Resolved here rather
       * than passed as `extra`: this screen cannot change it, so there is nothing to keep in
       * step.
       */
      accuracyThreshold: resolveAccuracyThreshold(extra),
    });
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
            status === OVERLAP_STATUS.notValidated &&
            failures.map((failure) => (
              <Text
                key={failure.id || failure.key}
                testID={`text-polygon-warning-${failure.key}`}
                style={styles.polygonWarningText}
              >
                {`⚠ ${formatRuleFailure(failure, trans)}`}
              </Text>
            ))}
          <View style={styles.polygonReport}>
            {checking && (
              <Text testID="text-polygon-checking" style={styles.polygonReportChecking}>
                {trans.polygonValidating}
              </Text>
            )}
            {!checking && pendingNotice && (
              <Text testID="text-polygon-not-validated" style={styles.polygonWarningText}>
                {`\u26A0 ${pendingNotice}`}
              </Text>
            )}
            {!checking && status === OVERLAP_STATUS.passed && (
              <Text testID="text-polygon-validated" style={styles.polygonReportPass}>
                {`✓ ${trans.polygonValidationPassed}`}
              </Text>
            )}
            {!checking &&
              reportFailures.map((failure) => (
                <Text
                  key={failure.id || failure.key}
                  testID={`text-polygon-report-${failure.key}`}
                  style={styles.polygonReportFail}
                >
                  {formatRuleFailure(failure, trans)}
                </Text>
              ))}
          </View>
        </View>
        <View style={styles.geoButtonGroup}>
          <Button onPress={handleDraw} testID="button-draw-on-map" disabled={disabled}>
            {trans.buttonDrawOnMap}
          </Button>
          {showValidate && (
            <Button
              onPress={handleValidate}
              testID="button-validate-polygon"
              disabled={disabled || checking}
            >
              {trans.buttonValidatePolygon}
            </Button>
          )}
          {!checking && status === OVERLAP_STATUS.unavailable && stored?.retryable && (
            <Button onPress={handleRetrySync} testID="button-retry-sync" disabled={disabled}>
              {trans.buttonRetrySync}
            </Button>
          )}
          {showReviewMap && (
            <Button
              onPress={handleReviewOverlaps}
              testID="button-review-overlaps"
              disabled={disabled}
            >
              {trans.buttonViewOverlaps}
            </Button>
          )}
        </View>
      </View>
    </View>
  );
};

export default TypeGeoDrawing;
