"""
Pre-download Photos Command

This command downloads photos from CSV data URLs before running the
flow_data_seeder. It creates a success log for URL->local_path mapping
and a failed log for manual review.

Usage:
    python manage.py predownload_photos -f <flow_form_id>

Examples:
    # Download photos for form 123 with default 5 workers
    python manage.py predownload_photos -f 123

    # Download with 10 concurrent workers
    python manage.py predownload_photos -f 123 --workers 10
"""

import logging
from django.core.management import BaseCommand

from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions

from utils.seeder_config import (
    SeederConfig,
    ValidationError,
    ConfigurationError,
    validate_configuration,
    get_form_by_flow_id,
    NON_QUESTION_COLUMNS,
)
from utils.seeder_data_loader import load_and_prepare_data
from utils.seeder_photo_downloader import PhotoPreDownloader

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command for pre-downloading photos."""

    help = "Pre-download photos from CSV before running flow_data_seeder"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "-f",
            "--form",
            type=int,
            required=True,
            help="Akvo Flow form ID",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=5,
            help="Number of concurrent download workers (default: 5)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of records to process",
        )

    def handle(self, *args, **options):
        """Main entry point - orchestrates photo downloading."""
        try:
            flow_form_id = options.get("form")
            workers = options.get("workers", 5)
            limit = options.get("limit")

            # Validate form_id
            if flow_form_id <= 0:
                raise ValidationError("Form ID must be a positive integer")

            # Create config for data loading
            config = SeederConfig(
                flow_form_id=flow_form_id,
                limit=limit,
            )
            validate_configuration(config)

            # Validate form exists
            get_form_by_flow_id(flow_form_id)

            self._log_info(
                f"\n{'='*60}\n"
                f"Pre-downloading Photos\n"
                f"Flow Form ID: {flow_form_id}\n"
                f"Workers: {workers}\n"
            )

            # 1. Load CSV data (parent + child dict)
            parent_df, child_data_dict = load_and_prepare_data(config)

            if parent_df is None or parent_df.empty:
                self._log_warning("No parent data found. Nothing to download.")
                return

            # 2. Get photo questions from the DataFrame columns
            photo_questions = self._get_photo_questions(
                parent_df, child_data_dict
            )

            if not photo_questions:
                self._log_info("No photo questions found in the form.")
                return

            self._log_info(
                f"Found {len(photo_questions)} photo question(s)"
            )

            # 3. Extract URLs with context from all data
            all_entries = []

            # Extract from parent data
            extractor = PhotoPreDownloader.extract_photo_urls_with_context
            parent_entries = extractor(
                df=parent_df, photo_questions=photo_questions
            )
            all_entries.extend(parent_entries)

            # Extract from child data if exists (now a dict of DataFrames)
            if child_data_dict:
                for form_id, child_df in child_data_dict.items():
                    if child_df is not None and not child_df.empty:
                        child_entries = extractor(
                            df=child_df, photo_questions=photo_questions
                        )
                        all_entries.extend(child_entries)

            if not all_entries:
                self._log_info("No photo URLs found in the data.")
                return

            self._log_info(f"Found {len(all_entries)} photo URL(s) to process")

            # 4. Initialize downloader
            downloader = PhotoPreDownloader(
                form_id=flow_form_id,
                workers=workers,
            )

            # 5. Load existing success log (skip already downloaded)
            existing = downloader.load_success_log()
            if existing:
                self._log_info(
                    f"Found {len(existing)} already downloaded photo(s)"
                )

            # 6. Download concurrently with progress
            def print_progress(done, total):
                self.stdout.write(
                    f"\rDownloading: {done}/{total}",
                    ending=''
                )
                self.stdout.flush()

            success, failed = downloader.download_photos(
                photo_entries=all_entries,
                existing_success=existing,
                progress_callback=print_progress,
            )

            # 7. Print summary
            self.stdout.write("")  # New line after progress
            self._log_success(f"Downloaded: {success}")

            if failed > 0:
                self._log_warning(f"Failed: {failed}")
                failed_path = downloader.get_failed_log_path()
                self._log_warning(f"Review failed downloads: {failed_path}")
            skipped = len(all_entries) - success - failed
            if skipped > 0:
                self._log_info(f"Skipped (already downloaded): {skipped}")

            self._log_info(
                f"Success log: {downloader.get_success_log_path()}"
            )

        except ValidationError as e:
            self._log_error(str(e))
        except ConfigurationError as e:
            self._log_error(str(e))
        except Exception as e:
            self._log_error(f"Unexpected error: {e}")
            logger.exception("Unexpected error during photo download")
            raise

    def _get_photo_questions(self, parent_df, child_data_dict):
        """Get photo questions from DataFrame columns.

        Args:
            parent_df: Parent DataFrame
            child_data_dict: Dict mapping form_id to child DataFrame

        Returns:
            List of Question objects with type=photo
        """
        # Collect all question IDs from parent and all child DataFrames
        question_ids = set()

        # Process parent DataFrame
        if parent_df is not None and not parent_df.empty:
            for col in parent_df.columns:
                if col not in NON_QUESTION_COLUMNS:
                    try:
                        question_ids.add(int(float(col)))
                    except (ValueError, TypeError):
                        continue

        # Process child DataFrames (dict)
        if child_data_dict:
            for form_id, child_df in child_data_dict.items():
                if child_df is None or child_df.empty:
                    continue
                for col in child_df.columns:
                    if col not in NON_QUESTION_COLUMNS:
                        try:
                            question_ids.add(int(float(col)))
                        except (ValueError, TypeError):
                            continue

        if not question_ids:
            return []

        # Query for photo type questions
        return list(
            Questions.objects.filter(
                pk__in=question_ids,
                type=QuestionTypes.image,
            )
        )

    # =========================================================================
    # Logging Helpers
    # =========================================================================

    def _log_info(self, message: str):
        """Log info message."""
        logger.info(message)
        self.stdout.write(self.style.HTTP_INFO(message))

    def _log_success(self, message: str):
        """Log success message."""
        logger.info(message)
        self.stdout.write(self.style.SUCCESS(message))

    def _log_warning(self, message: str):
        """Log warning message."""
        logger.warning(message)
        self.stdout.write(self.style.WARNING(message))

    def _log_error(self, message: str):
        """Log error message."""
        logger.error(message)
        self.stdout.write(self.style.ERROR(message))
