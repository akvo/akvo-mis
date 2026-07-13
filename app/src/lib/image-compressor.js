import * as ImageManipulator from 'expo-image-manipulator';
import * as FileSystem from 'expo-file-system';

/**
 * Image quality presets for compression
 * Each preset defines maxWidth, quality, and a size threshold for skipping compression
 */
export const IMAGE_QUALITY_PRESETS = {
  low: {
    label: 'Low',
    value: 'low',
    maxWidth: 640,
    quality: 0.6,
    skipThreshold: 200 * 1024, // Skip if already < 200KB
    description: 'Smallest file size, fastest sync',
  },
  medium: {
    label: 'Medium',
    value: 'medium',
    maxWidth: 1024,
    quality: 0.75,
    skipThreshold: 500 * 1024, // Skip if already < 500KB
    description: 'Balanced quality and size',
  },
  high: {
    label: 'High',
    value: 'high',
    maxWidth: 1600,
    quality: 0.85,
    skipThreshold: 500 * 1024, // Skip if already < 500KB
    description: 'Better quality, larger files',
  },
  original: {
    label: 'Original',
    value: 'original',
    maxWidth: null,
    quality: 1.0,
    skipThreshold: null, // Never skip, always use original
    description: 'No compression',
  },
};

/**
 * Default quality preset
 */
export const DEFAULT_IMAGE_QUALITY = 'low';

/**
 * Get file size in bytes
 * @param {string} uri - File URI
 * @returns {Promise<number>} File size in bytes
 */
export const getFileSize = async (uri) => {
  try {
    const fileInfo = await FileSystem.getInfoAsync(uri);
    return fileInfo.size || 0;
  } catch (error) {
    console.error('[ImageCompressor] Error getting file size:', error);
    return 0;
  }
};

/**
 * Format file size for display
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted size string (e.g., "324 KB")
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) {
    return '0 B';
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${Math.round(kb)} KB`;
  }
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
};

/**
 * Moves a captured file out of the OS-purgeable cache directory into
 * documentDirectory, so pending submissions never lose their files to a
 * cache purge. Returns the new URI, or the original one if the move fails.
 * @param {string} uri - File URI (typically in cacheDirectory)
 * @param {string} subDir - documentDirectory subfolder ('images', 'attachments')
 * @returns {Promise<string>}
 */
export const persistImage = async (uri, subDir = 'images') => {
  try {
    const dir = `${FileSystem.documentDirectory}${subDir}`;
    const { exists } = await FileSystem.getInfoAsync(dir);
    if (!exists) {
      await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
    }
    const to = `${dir}/${Date.now()}_${uri.split('/').pop()}`;
    await FileSystem.moveAsync({ from: uri, to });
    return to;
  } catch (error) {
    console.error('[ImageCompressor] Persist failed, keeping cache uri:', error);
    return uri;
  }
};

/**
 * Compress an image based on quality preset
 * @param {string} uri - Original image URI
 * @param {string} qualityPreset - Quality preset key ('low', 'medium', 'high', 'original')
 * @returns {Promise<{uri: string, size: number, compressed: boolean}>}
 */
export const compressImage = async (uri, qualityPreset = DEFAULT_IMAGE_QUALITY) => {
  const preset = IMAGE_QUALITY_PRESETS[qualityPreset] || IMAGE_QUALITY_PRESETS[DEFAULT_IMAGE_QUALITY];

  // If original preset, return as-is with file size
  if (qualityPreset === 'original' || !preset.maxWidth) {
    const size = await getFileSize(uri);
    return { uri, size, compressed: false };
  }

  try {
    // Get original file size
    const originalSize = await getFileSize(uri);

    // Skip compression if file is already small enough
    if (preset.skipThreshold && originalSize < preset.skipThreshold) {
      return { uri, size: originalSize, compressed: false };
    }

    // Compress the image
    const result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: preset.maxWidth } }],
      {
        compress: preset.quality,
        format: ImageManipulator.SaveFormat.JPEG,
      },
    );

    // Get compressed file size
    const compressedSize = await getFileSize(result.uri);

    // If compression didn't help (rare edge case), use original
    if (compressedSize >= originalSize) {
      return { uri, size: originalSize, compressed: false };
    }

    return {
      uri: result.uri,
      size: compressedSize,
      compressed: true,
    };
  } catch (error) {
    console.error('[ImageCompressor] Compression failed, using original:', error);
    // Fallback to original on error
    const size = await getFileSize(uri);
    return { uri, size, compressed: false };
  }
};

/**
 * Get quality preset options for Settings dropdown
 * @returns {Array<{label: string, value: string}>}
 */
export const getQualityOptions = () =>
  Object.values(IMAGE_QUALITY_PRESETS).map(({ label, value }) => ({
    label,
    value,
  }));
