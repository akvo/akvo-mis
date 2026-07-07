import * as ImageManipulator from 'expo-image-manipulator';
import * as FileSystem from 'expo-file-system';
import {
  IMAGE_QUALITY_PRESETS,
  DEFAULT_IMAGE_QUALITY,
  getFileSize,
  formatFileSize,
  compressImage,
  getQualityOptions,
} from '../image-compressor';

jest.mock('expo-image-manipulator');
jest.mock('expo-file-system');

describe('image-compressor tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('IMAGE_QUALITY_PRESETS', () => {
    it('should have all required presets', () => {
      expect(IMAGE_QUALITY_PRESETS).toHaveProperty('low');
      expect(IMAGE_QUALITY_PRESETS).toHaveProperty('medium');
      expect(IMAGE_QUALITY_PRESETS).toHaveProperty('high');
      expect(IMAGE_QUALITY_PRESETS).toHaveProperty('original');
    });

    it('should have correct low preset values', () => {
      expect(IMAGE_QUALITY_PRESETS.low.maxWidth).toBe(640);
      expect(IMAGE_QUALITY_PRESETS.low.quality).toBe(0.6);
    });

    it('should have correct original preset values', () => {
      expect(IMAGE_QUALITY_PRESETS.original.maxWidth).toBeNull();
      expect(IMAGE_QUALITY_PRESETS.original.quality).toBe(1.0);
    });
  });

  describe('DEFAULT_IMAGE_QUALITY', () => {
    it('should default to low', () => {
      expect(DEFAULT_IMAGE_QUALITY).toBe('low');
    });
  });

  describe('formatFileSize', () => {
    it('should format 0 bytes', () => {
      expect(formatFileSize(0)).toBe('0 B');
    });

    it('should format bytes to KB', () => {
      expect(formatFileSize(1024)).toBe('1 KB');
      expect(formatFileSize(512)).toBe('1 KB');
      expect(formatFileSize(324 * 1024)).toBe('324 KB');
    });

    it('should format bytes to MB', () => {
      expect(formatFileSize(1024 * 1024)).toBe('1.0 MB');
      expect(formatFileSize(2.5 * 1024 * 1024)).toBe('2.5 MB');
    });
  });

  describe('getFileSize', () => {
    it('should return file size from FileSystem', async () => {
      FileSystem.getInfoAsync.mockResolvedValue({ size: 500000 });
      const size = await getFileSize('file://test.jpg');
      expect(size).toBe(500000);
    });

    it('should return 0 on error', async () => {
      FileSystem.getInfoAsync.mockRejectedValue(new Error('File not found'));
      const size = await getFileSize('file://nonexistent.jpg');
      expect(size).toBe(0);
    });

    it('should return 0 if size is undefined', async () => {
      FileSystem.getInfoAsync.mockResolvedValue({});
      const size = await getFileSize('file://test.jpg');
      expect(size).toBe(0);
    });
  });

  describe('compressImage', () => {
    const mockUri = 'file://original.jpg';
    const mockCompressedUri = 'file://compressed.jpg';

    it('should return original for "original" preset', async () => {
      FileSystem.getInfoAsync.mockResolvedValue({ size: 1000000 });
      const result = await compressImage(mockUri, 'original');

      expect(result.uri).toBe(mockUri);
      expect(result.compressed).toBe(false);
      expect(ImageManipulator.manipulateAsync).not.toHaveBeenCalled();
    });

    it('should skip compression if file is below threshold', async () => {
      // File is 100KB, threshold for low is 200KB
      FileSystem.getInfoAsync.mockResolvedValue({ size: 100 * 1024 });
      const result = await compressImage(mockUri, 'low');

      expect(result.uri).toBe(mockUri);
      expect(result.compressed).toBe(false);
      expect(ImageManipulator.manipulateAsync).not.toHaveBeenCalled();
    });

    it('should compress image when above threshold', async () => {
      FileSystem.getInfoAsync
        .mockResolvedValueOnce({ size: 5 * 1024 * 1024 }) // Original: 5MB
        .mockResolvedValueOnce({ size: 200 * 1024 }); // Compressed: 200KB

      ImageManipulator.manipulateAsync.mockResolvedValue({ uri: mockCompressedUri });

      const result = await compressImage(mockUri, 'low');

      expect(result.uri).toBe(mockCompressedUri);
      expect(result.compressed).toBe(true);
      expect(result.size).toBe(200 * 1024);
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        mockUri,
        [{ resize: { width: 640 } }],
        { compress: 0.6, format: ImageManipulator.SaveFormat.JPEG },
      );
    });

    it('should use original if compression does not help', async () => {
      const originalSize = 100 * 1024;
      FileSystem.getInfoAsync
        .mockResolvedValueOnce({ size: originalSize })
        .mockResolvedValueOnce({ size: originalSize + 1000 }); // Compressed is larger

      ImageManipulator.manipulateAsync.mockResolvedValue({ uri: mockCompressedUri });

      // Force compression by using high preset with larger threshold
      const result = await compressImage(mockUri, 'high');

      expect(result.uri).toBe(mockUri);
      expect(result.compressed).toBe(false);
    });

    it('should fallback to original on error', async () => {
      FileSystem.getInfoAsync
        .mockResolvedValueOnce({ size: 5 * 1024 * 1024 })
        .mockResolvedValueOnce({ size: 5 * 1024 * 1024 });

      ImageManipulator.manipulateAsync.mockRejectedValue(new Error('Compression failed'));

      const result = await compressImage(mockUri, 'low');

      expect(result.uri).toBe(mockUri);
      expect(result.compressed).toBe(false);
    });

    it('should use default preset if invalid preset provided', async () => {
      FileSystem.getInfoAsync.mockResolvedValue({ size: 100 * 1024 });
      const result = await compressImage(mockUri, 'invalid_preset');

      // Should use low preset defaults and skip compression (100KB < 200KB threshold)
      expect(result.compressed).toBe(false);
    });
  });

  describe('getQualityOptions', () => {
    it('should return array of options', () => {
      const options = getQualityOptions();

      expect(Array.isArray(options)).toBe(true);
      expect(options.length).toBe(4);
    });

    it('should have label and value for each option', () => {
      const options = getQualityOptions();

      options.forEach((option) => {
        expect(option).toHaveProperty('label');
        expect(option).toHaveProperty('value');
      });
    });

    it('should include all presets', () => {
      const options = getQualityOptions();
      const values = options.map((o) => o.value);

      expect(values).toContain('low');
      expect(values).toContain('medium');
      expect(values).toContain('high');
      expect(values).toContain('original');
    });
  });
});
