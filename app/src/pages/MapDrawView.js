import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  View,
  StyleSheet,
  ActivityIndicator,
  Alert,
  TouchableOpacity,
  BackHandler,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { Button, Text, Icon, Dialog } from '@rneui/themed';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { FormState, UserState } from '../store';
import i18n from '../lib/i18n';
import loadMapDrawHtml from '../lib/map-draw-html';
import { polygonAreaHectares } from '../form/lib/geometry';
import {
  DEFAULT_INTERVAL_SECONDS,
  INTERVAL_OPTIONS,
  accuracyThreshold as resolveAccuracyThreshold,
  configuredAccuracyThreshold,
  formatInterval,
  hasSatelliteLock,
  poorVertexCount,
  selectableAccuracyOptions,
  tappingAllowed,
} from '../form/lib/gps-vertex';
import {
  areaIsAmbiguous,
  failedRules,
  formatRuleFailure,
  runPolygonRules,
} from '../form/lib/polygon-rules';
import useBoundaryRecorder from '../hooks/use-boundary-recorder';
import { QUESTION_TYPES } from '../lib/constants';

const CLEAR_CONFIRM_THRESHOLD = 3;
const MIN_POINTS_FOR_AREA = 3;

/**
 * ODK Collect's geoshape screen offers three capture modes, in ODK's order so the two apps
 * stay learnable together. GEO-001 shipped tapping and listed the two recording modes
 * disabled; GEO-004 fills them in, which is why this task adds no new chrome.
 */
const INPUT_METHODS = [
  { key: 'tapping', labelKey: 'inputMethodTapping' },
  { key: 'manual', labelKey: 'inputMethodManual' },
  { key: 'automatic', labelKey: 'inputMethodAutomatic' },
];

/** The two that walk a boundary: both need a GPS fix before they can start. */
const RECORDING_METHODS = ['manual', 'automatic'];

const MapDrawView = ({ navigation, route }) => {
  const {
    id: questionID,
    value: initialValue = [],
    type = QUESTION_TYPES.geoshape,
    extra = null,
  } = route.params;
  // geoshape is a closed ring with an enclosed area; geotrace is an open line with
  // neither. Capture - tap, drag, undo, clear - is identical for both.
  const isClosed = type !== QUESTION_TYPES.geotrace;
  const [htmlContent, setHtmlContent] = useState(null);
  const [points, setPoints] = useState(initialValue || []);
  const [showInputMethod, setShowInputMethod] = useState(false);
  const [showWarnings, setShowWarnings] = useState(false);
  const [inputMethod, setInputMethod] = useState(() =>
    tappingAllowed(route.params?.extra) ? 'tapping' : 'automatic',
  );
  const [started, setStarted] = useState(false);
  /** null when nothing is being recorded; otherwise 'manual' or 'automatic'. */
  const [recordingMode, setRecordingMode] = useState(null);
  const [intervalSeconds, setIntervalSeconds] = useState(DEFAULT_INTERVAL_SECONDS);
  /** Which dropdown is expanded in the dialog, if any: 'interval' or 'accuracy'. */
  const [openPicker, setOpenPicker] = useState(null);
  const webViewRef = useRef(null);
  /**
   * This screen renders without a header and edge to edge, so the save button sits under
   * Android's gesture/navigation bar unless the bottom inset is padded out explicitly.
   */
  const insets = useSafeAreaInsets();
  const activeLang = FormState.useState((s) => s.lang);
  const savedLocation = UserState.useState((s) => s.currentLocation);
  const trans = i18n.text(activeLang);

  const command = useCallback((commandType, data) => {
    webViewRef.current?.postMessage(JSON.stringify({ type: commandType, data: data || {} }));
  }, []);

  /**
   * Metres, and the enumerator's to choose (GEO-004 D-7). Marks vertices red in this phase and
   * nothing more - the gate that blocks submission is phase 3 (GEO-014 D-6), so field testing
   * cannot deadlock on a bad stretch.
   */
  /**
   * `geoConfig.allowTapping: false` removes tap-to-draw, leaving GPS capture as the only way in
   * (GEO-014 D-4). A traced boundary is not evidence, and no real fix reads 0 m — but it is the
   * form author's call, not a side effect of switching overlap detection on.
   */
  const canTap = useMemo(() => tappingAllowed(extra), [extra]);
  const accuracyCap = useMemo(() => configuredAccuracyThreshold(extra), [extra]);
  const accuracyOptions = useMemo(() => selectableAccuracyOptions(accuracyCap), [accuracyCap]);
  const [threshold, setThreshold] = useState(() => resolveAccuracyThreshold(extra));

  const handleVertex = useCallback(
    (vertex) => {
      command('addPoint', { point: vertex });
    },
    [command],
  );

  /**
   * Open the watch while the enumerator is still CHOOSING, not only once they have started.
   *
   * Without this the satellite-lock gate is circular: Start stays disabled until a fix arrives,
   * and no fix can arrive because the watch only opens after Start. The screen then falls back
   * to Home.js's fix, which is up to 60 s old and absent entirely until location permission has
   * been granted - so the button reads as permanently dead. ODK shows live accuracy while you
   * pick a mode for the same reason.
   */
  const recorderMode =
    recordingMode ||
    (showInputMethod && RECORDING_METHODS.includes(inputMethod) ? 'standby' : null);

  const { fix, recordNow } = useBoundaryRecorder({
    mode: recorderMode,
    onVertex: handleVertex,
    intervalSeconds,
  });

  /**
   * While recording, the session's own watch is the fresher of the two: Home.js reports every
   * 60 s (buildParams.gpsInterval), which is stale for someone walking. Idle, Home.js's fix is
   * all there is and the strip keeps working exactly as it did in GEO-001.
   */
  const liveLocation = fix || savedLocation;
  const accuracy = liveLocation?.coords?.accuracy;
  const locked = hasSatelliteLock(liveLocation);
  const poorCount = useMemo(() => poorVertexCount(points, threshold), [points, threshold]);

  /**
   * Advisory only - severity belongs to the submit gate, which this screen is not
   * (GEO-002 2.1.5). Recomputed on every vertex change, which is the point: this is the one
   * surface where the offending vertex is still on screen and still draggable.
   */
  const failures = useMemo(
    () => failedRules(runPolygonRules(points, { type, extra })),
    [points, type, extra],
  );
  // A self-crossing ring has no well-defined area, so the figure below is marked rather than
  // stated. GEO-003 D-6.
  const areaUnreliable = areaIsAmbiguous(failures);

  const loadHtml = useCallback(async () => {
    /**
     * Read once, from the raw state rather than the subscribed value: Home.js pushes a new
     * currentLocation on every GPS fix, and keying this on it would rebuild the page - and
     * discard the polygon - every few seconds. Live position goes over the bridge below.
     */
    const coords = UserState.getRawState()?.currentLocation?.coords;
    const html = await loadMapDrawHtml({
      points: initialValue || [],
      center: coords ? [coords.latitude, coords.longitude] : [0, 0],
      myLocation: coords ? [coords.latitude, coords.longitude, coords.accuracy] : null,
      closed: isClosed,
      // Read once, like initialValue and for the same reason. The enumerator can change this
      // mid-capture, and rebuilding the page to recolour vertices would discard the polygon
      // they are standing in the middle of; changes go over the bridge below instead.
      accuracyThreshold: resolveAccuracyThreshold(extra),
    });
    setHtmlContent(html);
    // initialValue is the value captured when the screen was pushed; it is deliberately
    // read once and not tracked, the WebView owns the geometry from then on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClosed]);

  useEffect(() => {
    loadHtml();
  }, [loadHtml]);

  // Recolour in place when the enumerator picks a different accuracy. 0 is the page's "no
  // marking", which is what ODK's "None" means here.
  useEffect(() => {
    if (!htmlContent) {
      return;
    }
    command('setAccuracyThreshold', { threshold: threshold || 0 });
  }, [htmlContent, threshold, command]);

  // Keep the blue dot and its accuracy circle following the live fix.
  useEffect(() => {
    const coords = liveLocation?.coords;
    if (!htmlContent || !coords) {
      return;
    }
    command('setMyLocation', {
      lat: coords.latitude,
      lng: coords.longitude,
      accuracy: coords.accuracy,
    });
  }, [htmlContent, liveLocation, command]);

  /**
   * FormPage keeps a hardwareBackPress listener registered while this screen sits on top of it
   * (FormPage.js:293 has no focus guard), so without claiming the event here a back press is
   * handled by the form underneath - discarding the form or popping past it. Registered on
   * mount, so it runs before FormPage's and returns true to stop there.
   *
   * goBack, never navigate('FormPage'): React Navigation 6 REPLACES a route's params on
   * navigate unless merge is set, so navigating by name with no params blanks FormPage's
   * `id`, `name` and `newSubmission`. That turned a submit into an update of a row with no
   * id - a silent no-op that still reported success and lost the submission.
   *
   * Back discards, like Save is the only commit: the polygon is written to FormState by the
   * save control, never by leaving.
   */
  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (showInputMethod) {
        setShowInputMethod(false);
        return true;
      }
      // Without this a back press behind the warnings dialog would discard the polygon rather
      // than dismiss the dialog - the same trap the input-method branch above exists to avoid.
      if (showWarnings) {
        setShowWarnings(false);
        return true;
      }
      if (navigation.canGoBack()) {
        navigation.goBack();
      }
      return true;
    });
    return () => backHandler.remove();
  }, [navigation, showInputMethod, showWarnings]);

  const handleMessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.nativeEvent.data);
    } catch (err) {
      return;
    }
    if (message.type === 'polygonChanged') {
      setPoints(message.data.points);
    }
  };

  /**
   * Until a capture mode has been started the pin opens the input-method chooser, as in ODK.
   * After that it means "add a vertex here", and what "here" is depends on the mode: the map
   * centre while tapping, the enumerator's own position while recording. Recording from the
   * crosshair would silently let someone map a plot from the far side of a fence.
   */
  const handleAddPoint = () => {
    if (!started) {
      setShowInputMethod(true);
      return;
    }
    if (recordingMode) {
      recordNow();
      return;
    }
    command('addAtCenter');
  };

  const handleStartInputMethod = () => {
    // Belt and braces - the Start button is already disabled without a fix. Recording that
    // begins on no fix appends nothing, which reads as a frozen app rather than as a wait.
    if (RECORDING_METHODS.includes(inputMethod) && !locked) {
      return;
    }
    setShowInputMethod(false);
    setOpenPicker(null);
    setStarted(true);
    // Modes are exclusive, as in ODK: arming taps during a boundary walk would let a stray
    // touch on the map insert a vertex into the middle of the walked ring.
    const isTapping = inputMethod === 'tapping';
    command('setTapping', { enabled: isTapping });
    setRecordingMode(isTapping ? null : inputMethod);
  };

  /**
   * Stopping returns to the chooser rather than leaving a half-armed screen: `started` going
   * back to false is what makes the pin offer the modes again. The watch and the interval are
   * torn down by the recorder's own cleanup when `recordingMode` clears.
   */
  const handleStopRecording = () => {
    setRecordingMode(null);
    setStarted(false);
  };

  const handleUndo = () => {
    command('setPoints', { points: points.slice(0, -1) });
  };

  const handleClear = () => {
    if (points.length > CLEAR_CONFIRM_THRESHOLD) {
      Alert.alert(trans.confirmClearPolygonTitle, trans.confirmClearPolygon, [
        { text: trans.buttonCancel, style: 'cancel' },
        { text: trans.buttonOk, onPress: () => command('setPoints', { points: [] }) },
      ]);
      return;
    }
    command('setPoints', { points: [] });
  };

  const handleCentreOnMe = () => {
    const coords = savedLocation?.coords;
    if (!coords) {
      return;
    }
    command('centreOnMe', { lat: coords.latitude, lng: coords.longitude });
  };

  const handleSave = () => {
    FormState.update((s) => {
      s.currentValues = { ...s.currentValues, [questionID]: points };
    });
    navigation.goBack();
  };

  /**
   * ODK shows these as dropdowns. There is no picker component in this app and adding one for
   * two lists is not worth a dependency, so the row expands in place - same position, same
   * caret, same two taps to change a value.
   */
  const renderPicker = (key, label, options, selected, onSelect, format) => (
    <View>
      <TouchableOpacity
        style={styles.pickerRow}
        onPress={() => setOpenPicker(openPicker === key ? null : key)}
        testID={`picker-${key}`}
      >
        <Text style={styles.pickerLabel}>{label}</Text>
        <Text style={styles.pickerValue} testID={`picker-${key}-value`}>
          {`${format(selected)} \u25BE`}
        </Text>
      </TouchableOpacity>
      {openPicker === key &&
        options.map((option) => (
          <TouchableOpacity
            key={`${key}-${option}`}
            style={styles.pickerOption}
            onPress={() => {
              onSelect(option);
              setOpenPicker(null);
            }}
            testID={`picker-${key}-option-${option}`}
          >
            <Text style={[styles.methodLabel, option === selected && styles.pickerSelected]}>
              {format(option)}
            </Text>
          </TouchableOpacity>
        ))}
    </View>
  );

  const renderControl = (name, onPress, testID, options = {}) => {
    const { disabled = false, primary = false } = options;
    return (
      <TouchableOpacity
        onPress={onPress}
        disabled={disabled}
        testID={testID}
        style={[styles.control, primary && styles.controlPrimary, disabled && styles.disabled]}
      >
        <Icon type="material" name={name} size={24} color={primary ? '#ffffff' : '#1651b6'} />
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/*
        Two columns, not one row of everything: the live GPS state on the left, the running
        count on the right. The count moved up here from the status bar because that bar had
        run out of width - see the note on `statusBar` below.
      */}
      <View style={[styles.accuracyBar, { paddingTop: insets.top + 8 }]}>
        <View style={styles.accuracyBarLeft}>
          <Text style={styles.accuracyText} testID="text-accuracy">
            {trans.accuracyLabel}: {accuracy ? `${Math.round(accuracy)} m` : '-'}
          </Text>
          {/*
            Recording is the one state worth announcing on this bar: a boundary walk can run for
            half an hour, and "am I still recording?" is otherwise unanswerable without counting
            vertices. A live dot alone does not distinguish recording from idle.
          */}
          {recordingMode && (
            <Text style={[styles.accuracyText, styles.recordingText]} testID="text-recording">
              {`\u25CF ${trans.gpsRecording}`}
            </Text>
          )}
        </View>
        <Text style={styles.accuracyText} testID="text-point-count">
          {trans.pointsEntered}: {points.length}
        </Text>
      </View>

      <View style={styles.mapWrapper}>
        {!htmlContent && <ActivityIndicator />}
        {htmlContent && (
          <WebView
            ref={webViewRef}
            originWhitelist={['about:blank']}
            source={{ html: htmlContent }}
            style={styles.map}
            onMessage={handleMessage}
            testID="webview-map-draw"
          />
        )}

        <View style={styles.topControls}>
          {renderControl('my-location', handleCentreOnMe, 'button-centre-on-me')}
        </View>

        <View style={styles.bottomControls}>
          {recordingMode && renderControl('stop', handleStopRecording, 'button-stop-recording')}
          {renderControl('add-location', handleAddPoint, 'button-add-point')}
          {renderControl('backspace', handleUndo, 'button-undo', { disabled: !points.length })}
          {renderControl('delete', handleClear, 'button-clear', { disabled: !points.length })}
          {renderControl('save', handleSave, 'button-save-polygon', { primary: true })}
        </View>
      </View>

      {/*
        Verdicts only. The point count moved to the top bar because this row ran out of width:
        count + area + poor-accuracy + invalid overflowed on a 360 dp screen and clipped the
        last item mid-word, which is the one that matters most. `flexWrap` is the backstop -
        a longer translation or a three-digit count wraps to a second line rather than
        disappearing off the edge.
      */}
      <View style={[styles.statusBar, { paddingBottom: insets.bottom + 8 }]}>
        {isClosed && points.length >= MIN_POINTS_FOR_AREA && (
          <Text
            style={[styles.statusText, areaUnreliable && styles.statusWarningText]}
            testID="text-area"
          >
            {trans.polygonArea}: {areaUnreliable ? '~' : ''}
            {polygonAreaHectares(points).toFixed(2)} ha
          </Text>
        )}
        {/*
          Counted separately from the shape failures beside it, and never folded into them. A
          poor vertex is not an invalid shape - the ring is fine, one measurement is not - and
          the fix differs too: walk that stretch again rather than redraw the boundary.
        */}
        {poorCount > 0 && (
          <Text style={[styles.statusText, styles.statusPoorText]} testID="text-poor-accuracy">
            {`\u25CF ${trans.polygonPoorAccuracyCount.replace('{count}', poorCount)}`}
          </Text>
        )}
        {/*
          A count, not the sentences: a full message never fit here at any width, and the
          sentences live one tap away in the dialog. GEO-002 D-9.
        */}
        {failures.length > 0 && (
          <TouchableOpacity onPress={() => setShowWarnings(true)} testID="button-polygon-warnings">
            <Text style={[styles.statusText, styles.statusWarningText]}>
              {`\u26A0 ${trans.polygonInvalidCount.replace('{count}', failures.length)}`}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      <Dialog
        isVisible={showWarnings}
        onBackdropPress={() => setShowWarnings(false)}
        testID="dialog-polygon-warnings"
      >
        <Dialog.Title title={trans.polygonInvalidTitle} />
        {failures.map((failure) => (
          <Text
            key={failure.key}
            style={styles.warningRow}
            testID={`text-polygon-warning-${failure.key}`}
          >
            {`⚠ ${formatRuleFailure(failure, trans)}`}
          </Text>
        ))}
        <Dialog.Actions>
          <Button onPress={() => setShowWarnings(false)} testID="button-close-polygon-warnings">
            {trans.buttonOk}
          </Button>
        </Dialog.Actions>
      </Dialog>

      <Dialog isVisible={showInputMethod} testID="dialog-input-method">
        <Dialog.Title title={trans.inputMethodTitle} />
        {INPUT_METHODS.map(({ key, labelKey }) => {
          const disabled = key === 'tapping' && !canTap;
          return (
            <TouchableOpacity
              key={key}
              style={styles.methodRow}
              disabled={disabled}
              onPress={() => setInputMethod(key)}
              testID={`option-input-method-${key}`}
            >
              <Icon
                type="material"
                name={inputMethod === key ? 'radio-button-checked' : 'radio-button-unchecked'}
                size={22}
                color={disabled ? '#9e9e9e' : '#1651b6'}
              />
              <Text style={[styles.methodLabel, disabled && styles.methodLabelDisabled]}>
                {trans[labelKey]}
              </Text>
            </TouchableOpacity>
          );
        })}
        {/*
          Say why the row is greyed out. A disabled option with no reason reads as a broken app,
          and this one is a deliberate instruction from the form author.
        */}
        {!canTap && (
          <Text style={styles.methodHint} testID="text-tapping-disabled">
            {trans.gpsTappingDisabled}
          </Text>
        )}
        {/*
          ODK reveals the interval only under Automatic, and that is the right place for it -
          it means nothing in a mode that appends on demand. The accuracy control applies to
          both recording modes, since both mark what they record.
        */}
        {inputMethod === 'automatic' &&
          renderPicker(
            'interval',
            trans.gpsIntervalLabel,
            INTERVAL_OPTIONS,
            intervalSeconds,
            setIntervalSeconds,
            (value) => formatInterval(value, trans),
          )}
        {RECORDING_METHODS.includes(inputMethod) &&
          renderPicker(
            'accuracy',
            trans.gpsAccuracyFlagLabel,
            accuracyOptions,
            threshold,
            setThreshold,
            (value) => (value ? `${value} m` : trans.gpsAccuracyNone),
          )}
        {/*
          The form's threshold caps the list rather than freezing it (D-7), so say so once
          instead of leaving the missing options to be noticed - or not.
        */}
        {RECORDING_METHODS.includes(inputMethod) && accuracyCap !== null && (
          <Text style={styles.methodHint} testID="text-accuracy-capped">
            {trans.gpsAccuracyCapped.replace('{threshold}', accuracyCap)}
          </Text>
        )}
        {/*
          Names what is being waited for instead of leaving a dead Start button. A fix is all
          that is required - not a GOOD one: demanding accuracy under the threshold would
          refuse to start under canopy, which is where boundaries are walked, and it would
          contradict D-1, where poor fixes are recorded and marked rather than prevented.
        */}
        {RECORDING_METHODS.includes(inputMethod) && !locked && (
          <View style={styles.waitingRow} testID="text-waiting-for-fix">
            <ActivityIndicator size="small" color="#8a6d3b" />
            <Text style={styles.methodHint}>
              {accuracy
                ? trans.gpsImprovingFix.replace('{accuracy}', Math.round(accuracy))
                : trans.gpsWaitingForFix}
            </Text>
          </View>
        )}
        <Dialog.Actions>
          <Button
            onPress={handleStartInputMethod}
            disabled={RECORDING_METHODS.includes(inputMethod) && !locked}
            testID="button-start-input-method"
          >
            {trans.buttonStart}
          </Button>
          <Button
            type="clear"
            onPress={() => {
              setShowInputMethod(false);
              setOpenPicker(null);
            }}
            testID="button-cancel-input-method"
          >
            {trans.buttonCancel}
          </Button>
        </Dialog.Actions>
      </Dialog>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d1b2a',
  },
  accuracyBar: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  // `flex-start` above, not `center`: the left column grows a second line while recording, and
  // centring would slide the count down with it for no reason.
  accuracyBarLeft: {
    flexShrink: 1,
  },
  accuracyText: {
    color: '#ffffff',
    fontSize: 14,
  },
  mapWrapper: {
    flex: 1,
    justifyContent: 'center',
  },
  map: {
    flex: 1,
  },
  topControls: {
    position: 'absolute',
    top: 16,
    right: 16,
    gap: 12,
  },
  bottomControls: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    gap: 12,
  },
  control: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: '#eaf2ff',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 3,
  },
  controlPrimary: {
    backgroundColor: '#0d4f73',
  },
  disabled: {
    opacity: 0.4,
  },
  statusBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    rowGap: 4,
    columnGap: 16,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  statusText: {
    color: '#ffffff',
    fontSize: 14,
  },
  statusWarningText: {
    color: '#ffcc80',
  },
  statusPoorText: {
    color: '#ff8a80',
  },
  recordingText: {
    color: '#ff8a80',
    fontWeight: '600',
  },
  warningRow: {
    fontSize: 15,
    paddingVertical: 8,
  },
  methodRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
  },
  methodLabel: {
    fontSize: 15,
    flexShrink: 1,
  },
  methodLabelDisabled: {
    color: '#9e9e9e',
  },
  methodHint: {
    color: '#8a6d3b',
    fontSize: 13,
    flexShrink: 1,
  },
  waitingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingBottom: 8,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 10,
    paddingLeft: 34,
  },
  pickerLabel: {
    fontSize: 15,
    flexShrink: 1,
  },
  pickerValue: {
    fontSize: 15,
    color: '#1651b6',
  },
  pickerOption: {
    paddingVertical: 8,
    paddingLeft: 34,
  },
  pickerSelected: {
    color: '#1651b6',
    fontWeight: '600',
  },
});

export default MapDrawView;
