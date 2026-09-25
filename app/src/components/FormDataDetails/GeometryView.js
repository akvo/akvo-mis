import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { WebView } from 'react-native-webview';
import { UIState } from '../../store';
import i18n from '../../lib/i18n';
import loadMapDrawHtml from '../../lib/map-draw-html';
import { currentTileSource } from '../../lib/map-tiles';
import { QUESTION_TYPES } from '../../lib/constants';
import { fitBoundsFor, polygonAreaHectares } from '../../form/lib/geometry';

const MIN_POINTS_FOR_AREA = 3;
const PREVIEW_HEIGHT = 200;

const toPoints = (answer) => {
  if (Array.isArray(answer)) {
    return answer;
  }
  if (typeof answer === 'string' && answer.startsWith('[')) {
    try {
      const parsed = JSON.parse(answer);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  }
  return [];
};

/**
 * Read-only geometry preview for the datapoint detail list.
 *
 * The map is loaded with interaction disabled (GEO-001 D-5): inside a SectionList a pannable
 * map would swallow the scroll gesture, so here it behaves as a picture of the shape.
 *
 * geoshape is a closed ring with an enclosed area; geotrace is an open line with neither.
 */
const GeometryView = ({ index, answer, type = QUESTION_TYPES.geoshape }) => {
  const [htmlContent, setHtmlContent] = useState(null);
  const activeLang = UIState.useState((s) => s.lang);
  const trans = i18n.text(activeLang);

  const points = toPoints(answer);
  const pointCount = points.length;
  const isClosed = type !== QUESTION_TYPES.geotrace;

  const loadHtml = useCallback(async () => {
    if (!pointCount) {
      return;
    }
    const tiles = await currentTileSource({ bounds: fitBoundsFor([points]) });
    const html = await loadMapDrawHtml({
      points,
      center: points[0],
      readonly: true,
      closed: isClosed,
      tileUrl: tiles.template,
    });
    setHtmlContent(html);
    // `points` is derived from `answer` on every render; keying the effect to the answer keeps
    // it from reloading the page on unrelated re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answer, pointCount, isClosed]);

  useEffect(() => {
    loadHtml();
  }, [loadHtml]);

  if (!pointCount) {
    return <Text testID={`text-answer-${index}`}>-</Text>;
  }

  return (
    <View testID={`text-type-geometry-${index}`} style={styles.container}>
      <View style={styles.mapWrapper}>
        {htmlContent ? (
          <WebView
            originWhitelist={['about:blank']}
            source={{ html: htmlContent }}
            style={styles.map}
            scrollEnabled={false}
            testID={`webview-geometry-${index}`}
          />
        ) : (
          <ActivityIndicator testID={`loading-geometry-${index}`} />
        )}
      </View>
      <View style={styles.readout}>
        <Text testID={`text-geometry-points-${index}`}>
          {trans.polygonPoints}: {pointCount}
        </Text>
        {isClosed && pointCount >= MIN_POINTS_FOR_AREA && (
          <Text testID={`text-geometry-area-${index}`}>
            {trans.polygonArea}: {polygonAreaHectares(points).toFixed(2)} ha
          </Text>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  mapWrapper: {
    height: PREVIEW_HEIGHT,
    width: '100%',
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: '#f2f2f2',
    justifyContent: 'center',
  },
  map: {
    flex: 1,
  },
  readout: {
    flexDirection: 'row',
    gap: 16,
    paddingTop: 8,
  },
});

export default GeometryView;
