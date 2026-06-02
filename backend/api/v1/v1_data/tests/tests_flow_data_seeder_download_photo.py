"""
Tests for DownloadPhotoProcessor and process_photo functionality.

This module tests the photo download and processing functionality
used by the Flow Data Seeder.
"""

import requests
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_forms.models import QuestionTypes
from utils.seeder_answer_processor import (
    AnswerProcessor,
    DownloadPhotoProcessor,
    IMAGE_MAGIC_BYTES,
    VALID_IMAGE_MIME_TYPES,
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class DownloadPhotoProcessorValidationTestCase(TestCase):
    """Test suite for DownloadPhotoProcessor validation methods."""

    def test_validate_image_content_jpeg(self):
        """Test validation of JPEG image content."""
        jpeg_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        result = DownloadPhotoProcessor.validate_image_content(jpeg_content)
        self.assertEqual(result, 'jpg')

    def test_validate_image_content_png(self):
        """Test validation of PNG image content."""
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        result = DownloadPhotoProcessor.validate_image_content(png_content)
        self.assertEqual(result, 'png')

    def test_validate_image_content_gif87a(self):
        """Test validation of GIF87a image content."""
        gif_content = b'GIF87a\x01\x00\x01\x00'
        result = DownloadPhotoProcessor.validate_image_content(gif_content)
        self.assertEqual(result, 'gif')

    def test_validate_image_content_gif89a(self):
        """Test validation of GIF89a image content."""
        gif_content = b'GIF89a\x01\x00\x01\x00'
        result = DownloadPhotoProcessor.validate_image_content(gif_content)
        self.assertEqual(result, 'gif')

    def test_validate_image_content_bmp(self):
        """Test validation of BMP image content."""
        bmp_content = b'BM\x00\x00\x00\x00'
        result = DownloadPhotoProcessor.validate_image_content(bmp_content)
        self.assertEqual(result, 'bmp')

    def test_validate_image_content_webp(self):
        """Test validation of WebP image content."""
        webp_content = b'RIFF\x00\x00\x00\x00WEBP'
        result = DownloadPhotoProcessor.validate_image_content(webp_content)
        self.assertEqual(result, 'webp')

    def test_validate_image_content_invalid(self):
        """Test validation of invalid content."""
        invalid_content = b'This is not an image'
        result = DownloadPhotoProcessor.validate_image_content(invalid_content)
        self.assertIsNone(result)

    def test_validate_image_content_empty(self):
        """Test validation of empty content."""
        empty_content = b''
        result = DownloadPhotoProcessor.validate_image_content(empty_content)
        self.assertIsNone(result)


@override_settings(USE_TZ=False, TEST_ENV=True)
class DownloadPhotoProcessorExtensionTestCase(TestCase):
    """Test suite for DownloadPhotoProcessor URL extension extraction."""

    def test_get_extension_from_url_jpg(self):
        """Test extraction of .jpg extension."""
        url = 'https://example.com/images/photo.jpg'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'jpg')

    def test_get_extension_from_url_jpeg(self):
        """Test extraction of .jpeg extension (converts to jpg)."""
        url = 'https://example.com/images/photo.jpeg'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'jpg')

    def test_get_extension_from_url_png(self):
        """Test extraction of .png extension."""
        url = 'https://example.com/images/photo.png'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'png')

    def test_get_extension_from_url_gif(self):
        """Test extraction of .gif extension."""
        url = 'https://example.com/images/animation.gif'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'gif')

    def test_get_extension_from_url_webp(self):
        """Test extraction of .webp extension."""
        url = 'https://example.com/images/photo.webp'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'webp')

    def test_get_extension_from_url_with_query_params(self):
        """Test extraction with query parameters."""
        url = 'https://example.com/images/photo.png?size=large&quality=high'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'png')

    def test_get_extension_from_url_no_extension(self):
        """Test default extension when URL has no extension."""
        url = 'https://example.com/images/photo'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'jpg')

    def test_get_extension_from_url_unknown_extension(self):
        """Test default extension for unknown extension."""
        url = 'https://example.com/images/file.xyz'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'jpg')

    def test_get_extension_from_url_case_insensitive(self):
        """Test case insensitive extension detection."""
        url = 'https://example.com/images/photo.PNG'
        result = DownloadPhotoProcessor.get_extension_from_url(url)
        self.assertEqual(result, 'png')


@override_settings(USE_TZ=False, TEST_ENV=True)
class DownloadPhotoProcessorDownloadTestCase(TestCase):
    """Test suite for DownloadPhotoProcessor download functionality."""

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_success(self, mock_get):
        """Test successful image download."""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.iter_content.return_value = [b'image_data']
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/image.jpg'
        )

        self.assertEqual(result, b'image_data')
        mock_get.assert_called_once()

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_timeout(self, mock_get):
        """Test handling of timeout error."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_connection_error(self, mock_get):
        """Test handling of connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_http_error(self, mock_get):
        """Test handling of HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_too_large(self, mock_get):
        """Test handling of oversized image."""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        # Simulate a 60MB file (over 50MB limit)
        large_chunk = b'x' * (10 * 1024 * 1024)  # 10MB chunk
        mock_response.iter_content.return_value = [large_chunk] * 6
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/large_image.jpg'
        )

        self.assertIsNone(result)

    @patch('utils.seeder_answer_processor.requests.get')
    def test_download_image_unexpected_content_type(self, mock_get):
        """Test handling of unexpected content type (still downloads)."""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.iter_content.return_value = [b'image_data']
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = DownloadPhotoProcessor.download_image(
            'https://example.com/image.jpg'
        )

        # Should still return content (validation happens later)
        self.assertEqual(result, b'image_data')


@override_settings(USE_TZ=False, TEST_ENV=True)
class DownloadPhotoProcessorProcessTestCase(TestCase):
    """Test suite for DownloadPhotoProcessor.process method."""

    @patch('utils.seeder_answer_processor.storage.upload')
    @patch.object(DownloadPhotoProcessor, 'download_image')
    def test_process_success(self, mock_download, mock_upload):
        """Test successful image processing."""
        # JPEG magic bytes
        jpeg_content = b'\xff\xd8\xff\xe0' + b'rest_of_image'
        mock_download.return_value = jpeg_content
        mock_upload.return_value = './storage/images/seeder_test.jpg'

        result = DownloadPhotoProcessor.process(
            'https://example.com/image.jpg'
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('./storage/images/'))
        mock_download.assert_called_once_with('https://example.com/image.jpg')
        mock_upload.assert_called_once()

    @patch.object(DownloadPhotoProcessor, 'download_image')
    def test_process_download_failure(self, mock_download):
        """Test handling of download failure."""
        mock_download.return_value = None

        result = DownloadPhotoProcessor.process(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)

    @patch.object(DownloadPhotoProcessor, 'download_image')
    def test_process_invalid_image_content(self, mock_download):
        """Test handling of invalid image content."""
        mock_download.return_value = b'This is not an image file'

        result = DownloadPhotoProcessor.process(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)

    @patch('utils.seeder_answer_processor.storage.upload')
    @patch.object(DownloadPhotoProcessor, 'download_image')
    def test_process_storage_error(self, mock_download, mock_upload):
        """Test handling of storage upload error."""
        jpeg_content = b'\xff\xd8\xff\xe0' + b'rest_of_image'
        mock_download.return_value = jpeg_content
        mock_upload.side_effect = Exception("Storage error")

        result = DownloadPhotoProcessor.process(
            'https://example.com/image.jpg'
        )

        self.assertIsNone(result)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AnswerProcessorPhotoTestCase(TestCase):
    """Test suite for AnswerProcessor.process_photo method."""

    def setUp(self):
        """Clear shared photo URL map before each test."""
        AnswerProcessor.clear_photo_url_map()

    def tearDown(self):
        """Clear shared photo URL map after each test."""
        AnswerProcessor.clear_photo_url_map()

    def test_process_photo_none_value(self):
        """Test processing None value."""
        name, value, options = AnswerProcessor.process_photo(None)
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_photo_local_path(self):
        """Test processing local file path (non-URL)."""
        local_path = '/storage/images/existing_photo.jpg'
        name, value, options = AnswerProcessor.process_photo(local_path)
        self.assertEqual(name, local_path)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_photo_relative_path(self):
        """Test processing relative file path."""
        relative_path = 'images/photo.jpg'
        name, value, options = AnswerProcessor.process_photo(relative_path)
        self.assertEqual(name, relative_path)
        self.assertIsNone(value)
        self.assertIsNone(options)

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_url_success(self, mock_process):
        """Test successful URL processing."""
        mock_process.return_value = './storage/images/downloaded.jpg'

        name, value, options = AnswerProcessor.process_photo(
            'https://example.com/photo.jpg'
        )

        self.assertEqual(name, './storage/images/downloaded.jpg')
        self.assertIsNone(value)
        self.assertIsNone(options)
        mock_process.assert_called_once_with('https://example.com/photo.jpg')

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_url_failure_fallback(self, mock_process):
        """Test URL processing failure falls back to original value."""
        mock_process.return_value = None

        url = 'https://example.com/photo.jpg'
        name, value, options = AnswerProcessor.process_photo(url)

        self.assertEqual(name, url)
        self.assertIsNone(value)
        self.assertIsNone(options)

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_http_url(self, mock_process):
        """Test HTTP URL (non-HTTPS) processing."""
        mock_process.return_value = './storage/images/downloaded.jpg'

        name, value, options = AnswerProcessor.process_photo(
            'http://example.com/photo.jpg'
        )

        self.assertEqual(name, './storage/images/downloaded.jpg')
        mock_process.assert_called_once_with('http://example.com/photo.jpg')

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_url_with_whitespace(self, mock_process):
        """Test URL with leading/trailing whitespace."""
        mock_process.return_value = './storage/images/downloaded.jpg'

        name, value, options = AnswerProcessor.process_photo(
            '  https://example.com/photo.jpg  '
        )

        self.assertEqual(name, './storage/images/downloaded.jpg')
        mock_process.assert_called_once_with('https://example.com/photo.jpg')

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_uses_predownload_cache(self, mock_process):
        """Test that process_photo uses cached path without downloading."""
        # Set up pre-download cache
        cached_url = 'https://example.com/cached_photo.jpg'
        cached_path = '/images/seeder_12345_67.jpg'
        AnswerProcessor.set_photo_url_map({cached_url: cached_path})

        # Process the URL that's in the cache
        name, value, options = AnswerProcessor.process_photo(cached_url)

        # Should return cached path without calling DownloadPhotoProcessor
        self.assertEqual(name, cached_path)
        self.assertIsNone(value)
        self.assertIsNone(options)
        mock_process.assert_not_called()

    @patch.object(DownloadPhotoProcessor, 'process')
    def test_process_photo_downloads_when_not_in_cache(self, mock_process):
        """Test that process_photo downloads when URL is not in cache."""
        # Set up pre-download cache with a different URL
        AnswerProcessor.set_photo_url_map({
            'https://example.com/other.jpg': '/images/other.jpg'
        })
        mock_process.return_value = './storage/images/downloaded.jpg'

        # Process a URL that's NOT in the cache
        url = 'https://example.com/new_photo.jpg'
        name, value, options = AnswerProcessor.process_photo(url)

        # Should call DownloadPhotoProcessor since URL not in cache
        self.assertEqual(name, './storage/images/downloaded.jpg')
        mock_process.assert_called_once_with(url)

    def test_process_with_photo_question_type(self):
        """Test process method routes photo type correctly."""
        with patch.object(AnswerProcessor, 'process_photo') as mock_photo:
            mock_photo.return_value = ('result', None, None)

            name, value, options = AnswerProcessor.process(
                question_type=QuestionTypes.image,
                row_value='https://example.com/photo.jpg'
            )

            mock_photo.assert_called_once_with(
                'https://example.com/photo.jpg'
            )
            self.assertEqual(name, 'result')


@override_settings(USE_TZ=False, TEST_ENV=True)
class ImageMagicBytesTestCase(TestCase):
    """Test suite for IMAGE_MAGIC_BYTES constant."""

    def test_all_magic_bytes_defined(self):
        """Test that all expected image formats have magic bytes."""
        expected_formats = {'jpg', 'png', 'gif', 'webp', 'bmp'}
        defined_formats = set(IMAGE_MAGIC_BYTES.values())
        self.assertTrue(expected_formats.issubset(defined_formats))

    def test_magic_bytes_are_bytes(self):
        """Test that all magic bytes are byte strings."""
        for magic in IMAGE_MAGIC_BYTES.keys():
            self.assertIsInstance(magic, bytes)


@override_settings(USE_TZ=False, TEST_ENV=True)
class ValidImageMimeTypesTestCase(TestCase):
    """Test suite for VALID_IMAGE_MIME_TYPES constant."""

    def test_common_image_types_included(self):
        """Test that common image MIME types are included."""
        expected_types = {
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
        }
        self.assertTrue(expected_types.issubset(VALID_IMAGE_MIME_TYPES))

    def test_all_types_are_strings(self):
        """Test that all MIME types are strings."""
        for mime_type in VALID_IMAGE_MIME_TYPES:
            self.assertIsInstance(mime_type, str)
            self.assertTrue(mime_type.startswith('image/'))
