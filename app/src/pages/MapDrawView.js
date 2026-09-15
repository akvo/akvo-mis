import React, { useState, useRef, useEffect, useCallback } from 'react';
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

const CLEAR_CONFIRM_THRESHOLD = 3;
const MIN_POINTS_FOR_AREA = 3;

/**
 * ODK Collect's geoshape screen offers three capture modes. Only tapping ships in GEO-001;
 * both recording modes are GPS boundary walking and land with GEO-004, so they are listed
 * and disabled rather than hidden - the enumerator sees what the screen will eventually do,
 * and the option order matches ODK so the two apps stay learnable together.
 */
const INPUT_METHODS = [
  { key: 'tapping', labelKey: 'inputMethodTapping', enabled: true },
  { key: 'manual', labelKey: 'inputMethodManual', enabled: false },
  { key: 'automatic', labelKey: 'inputMethodAutomatic', enabled: false },
];

const MapDrawView = ({ navigation, route }) => {
  const { id: questionID, value: initialValue = [] } = route.params;
  const [htmlContent, setHtmlContent] = useState(null);
  const [points, setPoints] = useState(initialValue || []);
  const [showInputMethod, setShowInputMethod] = useState(false);
  const [inputMethod, setInputMethod] = useState('tapping');
  const [started, setStarted] = useState(false);
  const webViewRef = useRef(null);
  /**
   * This screen renders without a header and edge to edge, so the save button sits under
   * Android's gesture/navigation bar unless the bottom inset is padded out explicitly.
   */
  const insets = useSafeAreaInsets();
  const activeLang = FormState.useState((s) => s.lang);
  const savedLocation = UserState.useState((s) => s.currentLocation);
  const trans = i18n.text(activeLang);

  // Home.js already runs a watchPositionAsync into UserState, so accuracy is live here for free.
  const accuracy = savedLocation?.coords?.accuracy;

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
    });
    setHtmlContent(html);
    // initialValue is the value captured when the screen was pushed; it is deliberately
    // read once and not tracked, the WebView owns the geometry from then on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadHtml();
  }, [loadHtml]);

  // Keep the blue dot and its accuracy circle following the live fix.
  useEffect(() => {
    const coords = savedLocation?.coords;
    if (!htmlContent || !coords) {
      return;
    }
    webViewRef.current?.postMessage(
      JSON.stringify({
        type: 'setMyLocation',
        data: { lat: coords.latitude, lng: coords.longitude, accuracy: coords.accuracy },
      }),
    );
  }, [htmlContent, savedLocation]);

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
      if (navigation.canGoBack()) {
        navigation.goBack();
      }
      return true;
    });
    return () => backHandler.remove();
  }, [navigation, showInputMethod]);

  const command = (type, data) => {
    webViewRef.current?.postMessage(JSON.stringify({ type, data: data || {} }));
  };

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
   * Once tapping is running it does what it says and drops a vertex at the map centre.
   */
  const handleAddPoint = () => {
    if (!started) {
      setShowInputMethod(true);
      return;
    }
    command('addAtCenter');
  };

  const handleStartInputMethod = () => {
    setShowInputMethod(false);
    setStarted(true);
    if (inputMethod === 'tapping') {
      // Arms map taps in the page. Before this a touch only pans, so positioning the map
      // over a corner cannot drop a stray vertex.
      command('setTapping', { enabled: true });
    }
    // The two recording modes are disabled until GEO-004, so nothing else can be selected.
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
      <View style={[styles.accuracyBar, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.accuracyText} testID="text-accuracy">
          {trans.accuracyLabel}: {accuracy ? `${Math.round(accuracy)} m` : '-'}
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
          {renderControl('add-location', handleAddPoint, 'button-add-point')}
          {renderControl('backspace', handleUndo, 'button-undo', { disabled: !points.length })}
          {renderControl('delete', handleClear, 'button-clear', { disabled: !points.length })}
          {renderControl('save', handleSave, 'button-save-polygon', { primary: true })}
        </View>
      </View>

      <View style={[styles.statusBar, { paddingBottom: insets.bottom + 8 }]}>
        <Text style={styles.statusText} testID="text-point-count">
          {trans.pointsEntered}: {points.length}
        </Text>
        {points.length >= MIN_POINTS_FOR_AREA && (
          <Text style={styles.statusText} testID="text-area">
            {trans.polygonArea}: {polygonAreaHectares(points).toFixed(2)} ha
          </Text>
        )}
      </View>

      <Dialog isVisible={showInputMethod} testID="dialog-input-method">
        <Dialog.Title title={trans.inputMethodTitle} />
        {INPUT_METHODS.map(({ key, labelKey, enabled }) => (
          <TouchableOpacity
            key={key}
            style={styles.methodRow}
            disabled={!enabled}
            onPress={() => setInputMethod(key)}
            testID={`option-input-method-${key}`}
          >
            <Icon
              type="material"
              name={inputMethod === key ? 'radio-button-checked' : 'radio-button-unchecked'}
              size={22}
              color={enabled ? '#1651b6' : '#9e9e9e'}
            />
            <Text style={[styles.methodLabel, !enabled && styles.methodLabelDisabled]}>
              {trans[labelKey]}
              {enabled ? '' : ` (${trans.inputMethodComingSoon})`}
            </Text>
          </TouchableOpacity>
        ))}
        <Dialog.Actions>
          <Button
            type="clear"
            onPress={() => setShowInputMethod(false)}
            testID="button-cancel-input-method"
          >
            {trans.buttonCancel}
          </Button>
          <Button onPress={handleStartInputMethod} testID="button-start-input-method">
            {trans.buttonStart}
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
    paddingHorizontal: 16,
    paddingBottom: 8,
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
    gap: 16,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  statusText: {
    color: '#ffffff',
    fontSize: 14,
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
});

export default MapDrawView;
