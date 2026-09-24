import { Asset } from 'expo-asset';
import * as FileSystem from 'expo-file-system';

const escapeAttribute = (value) => JSON.stringify(value).replace(/"/g, '&quot;');

/**
 * Loads the bundled Leaflet page and substitutes the polygon into it.
 *
 * Values are baked into the HTML before the WebView loads rather than posted over the bridge,
 * so there is no message that can arrive before the page's JS has run. See GEO-001 section 6.2.
 */
const loadMapDrawHtml = async ({
  points = [],
  center = [0, 0],
  readonly = false,
  myLocation = null,
  closed = true,
  accuracyThreshold = 0,
}) => {
  // eslint-disable-next-line global-require
  const [{ localUri }] = await Asset.loadAsync(require('../../assets/map-draw.html'));
  const template = await FileSystem.readAsStringAsync(localUri);
  return (
    template
      .replace('{{points}}', () => escapeAttribute(points))
      .replace('{{center}}', () => escapeAttribute(center))
      .replace('{{readonly}}', () => `${readonly}`)
      .replace('{{myLocation}}', () => escapeAttribute(myLocation))
      .replace('{{closed}}', () => `${closed}`)
      // Baked in rather than posted, like everything else here: a vertex must never render in
      // the wrong colour for the window between load and the first bridge message. 0 disables
      // the marking entirely, which is what the read-only preview wants.
      .replace('{{accuracyThreshold}}', () => `${accuracyThreshold}`)
  );
};

export default loadMapDrawHtml;
