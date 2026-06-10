"""
Seeder Answer Processor Module

This module provides answer processing functionality for Flow Complete Seeder.
"""

import logging
import os
import tempfile
import uuid
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from api.v1.v1_forms.models import QuestionTypes
from utils import storage

logger = logging.getLogger(__name__)

# Valid image MIME types
VALID_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/bmp',
    'image/tiff',
}

# Image magic bytes for validation
IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpg',      # JPEG
    b'\x89PNG\r\n\x1a\n': 'png',  # PNG
    b'GIF87a': 'gif',            # GIF87a
    b'GIF89a': 'gif',            # GIF89a
    b'RIFF': 'webp',             # WebP (starts with RIFF)
    b'BM': 'bmp',                # BMP
}


# =============================================================================
# Download Photo Processor
# =============================================================================


class DownloadPhotoProcessor:
    """Handles downloading and validating photos from URLs."""

    @staticmethod
    def validate_image_content(content: bytes) -> Optional[str]:
        """Validate image content by checking magic bytes.

        Args:
            content: The raw bytes of the downloaded file

        Returns:
            The detected file extension if valid, None otherwise
        """
        for magic, ext in IMAGE_MAGIC_BYTES.items():
            if content.startswith(magic):
                return ext
        return None

    @staticmethod
    def get_extension_from_url(url: str) -> str:
        """Extract file extension from URL path.

        Args:
            url: The URL to extract extension from

        Returns:
            The file extension (without dot) or 'jpg' as default
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff']:
            if path.endswith(f'.{ext}'):
                return 'jpg' if ext == 'jpeg' else ext
        return 'jpg'

    @staticmethod
    def download_image(url: str, timeout: int = 30) -> Optional[bytes]:
        """Download image from URL with proper error handling.

        Args:
            url: The URL to download from
            timeout: Request timeout in seconds

        Returns:
            The image content as bytes, or None on failure
        """
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; AkvoMIS/1.0)'
                },
                stream=True
            )
            response.raise_for_status()

            # Check content type if available
            content_type = response.headers.get('Content-Type', '').lower()
            if content_type:
                mime_type = content_type.split(';')[0].strip()
                if mime_type and mime_type not in VALID_IMAGE_MIME_TYPES:
                    # Allow unknown content types but log a warning
                    logger.warning(
                        f"Unexpected content type '{mime_type}' for URL: {url}"
                    )

            # Limit download size to 50MB
            max_size = 50 * 1024 * 1024
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    logger.warning(f"Image too large (>50MB): {url}")
                    return None

            return content

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout downloading image from: {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error downloading image from: {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error {e.response.status_code} for: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error downloading image: {e}")
            return None

    @classmethod
    def process(cls, url: str) -> Optional[str]:
        """Download, validate, and store an image from a URL.

        Args:
            url: The URL to download the image from

        Returns:
            The local storage path if successful, None otherwise
        """
        # Download the image
        content = cls.download_image(url)
        if content is None:
            logger.warning(f"Failed to download image: {url}")
            return None

        # Validate image content by checking magic bytes
        detected_ext = cls.validate_image_content(content)
        if detected_ext is None:
            logger.warning(
                f"Downloaded content is not a valid image format: {url}"
            )
            return None

        # Use detected extension or fall back to URL extension
        extension = detected_ext or cls.get_extension_from_url(url)

        # Generate unique filename
        unique_id = uuid.uuid4().hex
        filename = f"seeder_{unique_id}.{extension}"

        # Save to temporary file then upload to storage
        tmp_file = None
        try:
            # Create temp file with proper extension
            with tempfile.NamedTemporaryFile(
                suffix=f'.{extension}',
                delete=False
            ) as tmp:
                tmp.write(content)
                tmp_file = tmp.name

            # Upload to storage/images
            stored_path = storage.upload(
                file=tmp_file,
                folder="images",
                filename=filename
            )

            logger.info(
                f"Successfully downloaded and stored image: {stored_path}"
            )
            return stored_path

        except Exception as e:
            logger.error(f"Error saving image to storage: {e}")
            return None

        finally:
            # Clean up temp file
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass


# =============================================================================
# Strategy Pattern for Answer Processing
# =============================================================================


class AnswerProcessor:
    """Strategy pattern for processing different question types."""

    OPTION_TYPES = [
        QuestionTypes.option,
        QuestionTypes.multiple_option,
    ]

    # Class-level cache populated by predownload_photos command
    photo_url_map: dict = {}

    @classmethod
    def set_photo_url_map(cls, url_map: dict):
        """Set the photo URL mapping from pre-download log.

        Args:
            url_map: Dictionary mapping URL to local storage path
        """
        cls.photo_url_map = url_map

    @classmethod
    def clear_photo_url_map(cls):
        """Clear the photo URL mapping."""
        cls.photo_url_map = {}

    @staticmethod
    def process_administration(
        row_value,
        administration_id: Optional[int],
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process administration-type questions.

        Args:
            row_value: The value from the CSV row
            administration_id: Administration ID to use

        Returns:
            Tuple of (name, value, options)
        """
        return None, administration_id, None

    @staticmethod
    def process_geo(
        row_value,
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process geo-type questions.

        Args:
            row_value: The value from the CSV row

        Returns:
            Tuple of (name, value, options)
        """
        if row_value is None:
            return None, None, None
        options = [
            float(g) for g in str(row_value).split("|")
        ]
        return None, None, options

    @staticmethod
    def process_option(
        row_value,
        opt_list: Optional[list] = [],
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process option-type questions.

        Args:
            row_value: The value from the CSV row

        Returns:
            Tuple of (name, value, options)
        """
        if row_value is None:
            return None, None, None
        option_values = str(row_value).split("|")
        # find intersection with opt_list to validate options
        option_values = [opt for opt in option_values if opt in opt_list]
        if not option_values:
            return None, None, None
        return None, None, option_values

    @staticmethod
    def process_number(
        row_value,
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process number-type questions.

        Args:
            row_value: The value from the CSV row

        Returns:
            Tuple of (name, value, options)
        """
        try:
            number_value = float(row_value)
            return None, number_value, None
        except (ValueError, TypeError):
            return None, None, None

    @classmethod
    def process_photo(
        cls,
        row_value,
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process photo-type questions.

        First checks the pre-downloaded cache (photo_url_map). If not found,
        downloads the photo from the given URL and uploads it to storage.
        Validates that the downloaded content is actually an image.

        Args:
            row_value: The value from the CSV row (expected to be a URL)

        Returns:
            Tuple of (name, value, options) where:
            - name: The local storage path if successful, original value
            - value: Always None for photos
            - options: Always None for photos
        """
        if row_value is None:
            return None, None, None

        url = str(row_value).strip()

        # If not a URL, return as-is (might be an existing local path)
        if not url.startswith(('http://', 'https://')):
            return row_value, None, None

        # Check pre-downloaded cache first
        if url in cls.photo_url_map:
            return cls.photo_url_map[url], None, None

        # Fallback: download on-demand using DownloadPhotoProcessor
        stored_path = DownloadPhotoProcessor.process(url)
        if stored_path is None:
            # Fall back to original value if download fails
            return row_value, None, None

        return stored_path, None, None

    @staticmethod
    def process_default(
        row_value,
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process default question types.

        Args:
            row_value: The value from the CSV row

        Returns:
            Tuple of (name, value, options)
        """
        return row_value, None, None

    @classmethod
    def process(
        cls,
        question_type: str,
        row_value,
        administration_id: Optional[int] = None,
        opt_list: Optional[list] = [],
        extra: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[int], Optional[list]]:
        """Process answer based on question type.

        Args:
            question_type: The type of question
            row_value: The value from the CSV row
            administration_id: Administration ID for admin-type questions
            extra: Question extra JSON (used to discriminate cascade sub-types)

        Returns:
            Tuple of (name, value, options)
        """
        if question_type == QuestionTypes.cascade:
            extra_type = (extra or {}).get("type")
            if extra_type == "entity":
                return cls.process_default(row_value)
            return cls.process_administration(row_value, administration_id)
        elif question_type == QuestionTypes.geo:
            return cls.process_geo(row_value)
        elif question_type in cls.OPTION_TYPES:
            return cls.process_option(row_value, opt_list)
        elif question_type == QuestionTypes.number:
            return cls.process_number(row_value)
        elif question_type == QuestionTypes.image:
            return cls.process_photo(row_value)
        else:
            return cls.process_default(row_value)
