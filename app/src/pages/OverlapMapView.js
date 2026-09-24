import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, StyleSheet, ActivityIndicator, BackHandler, TouchableOpacity } from 'react-native';
import { WebView } from 'react-native-webview';
import { Text, Icon } from '@rneui/themed';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { FormState } from '../store';
import i18n from '../lib/i18n';
import loadMapDrawHtml from '../lib/map-draw-html';
import { currentTileSource } from '../lib/map-tiles';
import { fitBoundsFor } from '../form/lib/geometry';
import { QUESTION_TYPES } from '../lib/constants';

/**
 * Read-only review of an overlap failure (GEO-008).
 *
 * The error under the field says `Overlaps 3 plots: #1 (34.0%), #2 (28.3%), #3 (22.5%)` and
 * deliberately names nobody: on a form with an administration cascade the generated datapoint
 * name is an administrative path six lines long, which identified nothing on device (GEO-007
 * D-11). So this screen carries the identity, and the `#n` here is position in the same
 * worst-first array the sentence was built from — sort it any other way and `#2` on the map is a
 * different plot from `#2` in the message.
 *
 * Nothing here can be edited (D-2). Two surfaces for one value is a synchronisation problem with
 * no compensating benefit; the enumerator reviews here and corrects in the field.
 */
const OverlapMapView = ({ navigation, route }) => {
  const {
    value: points = [],
    conflicts = [],
    name = null,
    type = QUESTION_TYPES.geoshape,
    accuracyThreshold = 0,
  } = route.params;

  const [htmlContent, setHtmlContent] = useState(null);
  /**
   * The resolver's verdict, not a connectivity check (D-1). A device can be offline and still
   * have imagery the moment a tile pack is downloaded, and the notice must not claim otherwise.
   *
   * `null` until it answers. Defaulting to "has tiles" would paint the out-of-date disclaimer for
   * one frame on a device that is about to be told there is no imagery at all.
   */
  const [hasTiles, setHasTiles] = useState(null);
  /** `null`, or `{ current: true }`, or one of the route's `conflicts`. */
  const [selected, setSelected] = useState(null);

  const insets = useSafeAreaInsets();
  const activeLang = FormState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const isClosed = type !== QUESTION_TYPES.geotrace;

  /**
   * Route params are fixed for the life of the screen, so this is read once rather than tracked
   * — the same reason MapDrawView does not re-bake its page on every GPS fix.
   */
  const fitBounds = useMemo(
    () => fitBoundsFor([points, ...conflicts.map((conflict) => conflict.coordinates)]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const loadHtml = useCallback(async () => {
    const tiles = await currentTileSource({ bounds: fitBounds });
    setHasTiles(tiles.hasTiles);
    const html = await loadMapDrawHtml({
      points,
      center: fitBounds ? fitBounds[0] : [0, 0],
      readonly: true,
      closed: isClosed,
      accuracyThreshold,
      tileUrl: tiles.template,
      review: true,
      /**
       * Label and coordinates only. A farmer's name never enters the WebView — it is rendered by
       * the panel below, from the same array, when the page reports a tap.
       */
      conflicts: conflicts.map(({ label, coordinates }) => ({ label, coordinates })),
      fitBounds,
    });
    setHtmlContent(html);
    // Everything this reads is a route param, fixed for the life of the screen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadHtml();
  }, [loadHtml]);

  /**
   * FormPage keeps a hardwareBackPress listener registered with no focus guard, so without
   * claiming the event here a back press is handled by the form underneath and discards it. The
   * same trap MapDrawView registers for.
   */
  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      if (navigation.canGoBack()) {
        navigation.goBack();
      }
      return true;
    });
    return () => backHandler.remove();
  }, [navigation]);

  const handleMessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.nativeEvent.data);
    } catch (err) {
      return;
    }
    if (message.type !== 'polygonTapped') {
      return;
    }
    const index = message.data?.index;
    if (index === null || index === undefined) {
      setSelected({ current: true });
      return;
    }
    const conflict = conflicts[Number(index)];
    if (conflict) {
      setSelected({ current: false, ...conflict });
    }
  };

  const renderLegendRow = (swatchStyle, label, testID) => (
    <View style={styles.legendRow}>
      <View style={[styles.swatch, swatchStyle]} />
      <Text style={styles.legendText} testID={testID}>
        {label}
      </Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <TouchableOpacity
          onPress={navigation.goBack}
          testID="button-close-overlap-map"
          style={styles.backButton}
        >
          <Icon type="material" name="arrow-back" size={24} color="#ffffff" />
        </TouchableOpacity>
        <View style={styles.headerText}>
          <Text style={styles.title}>{trans.overlapReviewTitle}</Text>
          {name ? <Text style={styles.subtitle}>{name}</Text> : null}
        </View>
      </View>

      <View style={styles.mapWrapper}>
        {!htmlContent && <ActivityIndicator />}
        {htmlContent && (
          <WebView
            originWhitelist={['about:blank']}
            source={{ html: htmlContent }}
            style={styles.map}
            onMessage={handleMessage}
            testID="webview-overlap-map"
          />
        )}

        {/*
          Mutually exclusive with the disclaimer below, and both come off the same verdict. No
          tiles means nothing to be out of date; tiles mean the shapes are drawn over a picture
          of the ground that nobody has promised is current.
        */}
        {hasTiles === false && (
          <View style={styles.notice}>
            <Text style={styles.noticeText} testID="text-imagery-offline">
              {trans.overlapImageryOffline}
            </Text>
          </View>
        )}

        <View style={styles.legend}>
          {renderLegendRow(styles.swatchCurrent, trans.overlapLegendCurrent)}
          {renderLegendRow(styles.swatchConflict, trans.overlapLegendConflict)}
          {/*
            0 is the page's "no marking", so a legend promising red dots that can never appear
            would be worse than none. And the wording is GPS quality, never verification
            (GEO-014 §8): a red dot says "this corner was measured loosely", not "this boundary
            is disputed" - the difference decides whether the enumerator re-walks a stretch or
            goes and knocks on a door.
          */}
          {accuracyThreshold > 0 &&
            renderLegendRow(
              styles.swatchPoor,
              trans.overlapLegendAccuracy.replace('{threshold}', accuracyThreshold),
              'text-legend-accuracy',
            )}
        </View>
      </View>

      <View style={[styles.footer, { paddingBottom: insets.bottom + 8 }]}>
        {selected && (
          <View style={styles.selected} testID="panel-selected">
            {!selected.current && (
              <Text style={styles.selectedLabel} testID="text-selected-label">
                {selected.label}
              </Text>
            )}
            <Text style={styles.selectedName} testID="text-selected-name">
              {selected.current ? trans.overlapCurrentPlot : selected.name || trans.overlapNoName}
            </Text>
            {!selected.current && selected.percent !== null && (
              <Text style={styles.selectedPercent} testID="text-selected-percent">
                {trans.overlapConflictPercent.replace('{percent}', selected.percent)}
              </Text>
            )}
          </View>
        )}
        {hasTiles && (
          <Text style={styles.disclaimer} testID="text-imagery-disclaimer">
            {trans.overlapImageryDisclaimer}
          </Text>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d1b2a',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: {
    flexShrink: 1,
  },
  title: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: '600',
  },
  subtitle: {
    color: '#c9d6e3',
    fontSize: 13,
  },
  mapWrapper: {
    flex: 1,
  },
  map: {
    flex: 1,
  },
  notice: {
    position: 'absolute',
    top: 12,
    left: 12,
    right: 12,
    borderRadius: 6,
    backgroundColor: 'rgba(13, 27, 42, 0.85)',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  noticeText: {
    color: '#ffffff',
    fontSize: 13,
  },
  legend: {
    position: 'absolute',
    bottom: 12,
    left: 12,
    borderRadius: 6,
    backgroundColor: 'rgba(13, 27, 42, 0.8)',
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 6,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  swatch: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
  },
  /**
   * The same three colours the Leaflet page draws with, restated here because the two runtimes
   * share nothing. `.vertex-poor` in `map-draw.html` is the one that has to match exactly: the
   * legend is explaining a dot the page drew.
   */
  swatchCurrent: {
    backgroundColor: '#00bcd4',
    borderColor: '#00697c',
    borderRadius: 2,
  },
  swatchConflict: {
    backgroundColor: '#ffb300',
    borderColor: '#9c6f00',
    borderRadius: 2,
  },
  swatchPoor: {
    backgroundColor: '#ec003f',
    borderColor: '#7a0020',
    borderWidth: 3,
  },
  legendText: {
    color: '#ffffff',
    fontSize: 12,
  },
  footer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    gap: 6,
  },
  selected: {
    gap: 2,
  },
  selectedLabel: {
    color: '#ffb300',
    fontSize: 15,
    fontWeight: '700',
  },
  selectedName: {
    color: '#ffffff',
    fontSize: 15,
  },
  selectedPercent: {
    color: '#c9d6e3',
    fontSize: 13,
  },
  disclaimer: {
    color: '#8fa3b5',
    fontSize: 12,
  },
});

export default OverlapMapView;
