"""
Tests for predownload_photos management command.

This module tests the photo pre-download command functionality,
including multi-child DataFrame support.

Run: ./dc.sh exec backend python manage.py test \
     api.v1.v1_data.tests.tests_predownload_photos_command -v2
"""

import pandas as pd
from unittest.mock import patch, MagicMock
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_forms.constants import QuestionTypes


@override_settings(USE_TZ=False, TEST_ENV=True)
class PredownloadPhotosArgumentsTestCase(TestCase):
    """Test suite for predownload_photos command argument parsing."""

    def test_argument_parser_required_form_flag(self):
        """Test that -f/--form flag is required."""
        out = StringIO()
        err = StringIO()

        with self.assertRaises(CommandError) as cm:
            call_command(
                "predownload_photos",
                stdout=out,
                stderr=err
            )
        self.assertIn("following arguments are required", str(cm.exception))

    def test_argument_parser_invalid_form_id(self):
        """Test that form ID must be positive."""
        out = StringIO()

        call_command(
            "predownload_photos",
            "-f", "0",
            stdout=out,
            stderr=StringIO()
        )

        output = out.getvalue()
        self.assertIn("Form ID must be a positive integer", output)

    def test_argument_parser_negative_form_id(self):
        """Test that negative form ID is rejected."""
        out = StringIO()

        call_command(
            "predownload_photos",
            "-f", "-1",
            stdout=out,
            stderr=StringIO()
        )

        output = out.getvalue()
        self.assertIn("Form ID must be a positive integer", output)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PredownloadPhotosGetPhotoQuestionsTestCase(TestCase):
    """Test suite for _get_photo_questions method with multi-child support."""

    def setUp(self):
        """Set up test environment with form and photo questions."""
        # Create test form
        self.form = Forms.objects.create(
            name="Test Form",
            version=1
        )

        # Create question group
        self.qg = QuestionGroup.objects.create(
            form=self.form,
            name="Test Group",
            order=1
        )

        # Create photo question
        self.photo_question = Questions.objects.create(
            form=self.form,
            question_group=self.qg,
            name="test_photo",
            label="Test Photo Question",
            order=1,
            type=QuestionTypes.image
        )

        # Create non-photo question
        self.text_question = Questions.objects.create(
            form=self.form,
            question_group=self.qg,
            name="test_text",
            label="Test Text Question",
            order=2,
            type=QuestionTypes.text
        )

    def test_get_photo_questions_from_parent_df(self):
        """Test extracting photo questions from parent DataFrame columns."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        # Parent DataFrame with photo question column
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1', 'uuid-2'],
            'datapoint_id': [1001, 1002],
            str(self.photo_question.pk): [
                'https://example.com/photo1.jpg',
                'https://example.com/photo2.jpg'
            ],
            str(self.text_question.pk): ['text1', 'text2'],
        })

        # Empty child dict
        child_data_dict = {}

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pk, self.photo_question.pk)
        self.assertEqual(result[0].type, QuestionTypes.image)

    def test_get_photo_questions_from_child_dict(self):
        """Test extracting photo questions from child DataFrame dict."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        # Empty parent DataFrame (only metadata columns)
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
        })

        # Child DataFrame dict with photo question column
        child_data_dict = {
            100: pd.DataFrame({
                'identifier': ['uuid-1'],
                'datapoint_id': [2001],
                str(self.photo_question.pk): [
                    'https://example.com/child_photo.jpg'
                ],
            })
        }

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pk, self.photo_question.pk)

    def test_get_photo_questions_from_multiple_child_forms(self):
        """Test extracting photo questions from multiple child DataFrames."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        # Create additional photo question for second child form
        photo_question_2 = Questions.objects.create(
            form=self.form,
            question_group=self.qg,
            name="test_photo_2",
            label="Test Photo Question 2",
            order=3,
            type=QuestionTypes.image
        )

        cmd = Command()

        # Parent DataFrame
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
        })

        # Multiple child DataFrames with different photo questions
        child_data_dict = {
            100: pd.DataFrame({
                'identifier': ['uuid-1'],
                'datapoint_id': [2001],
                str(self.photo_question.pk): [
                    'https://example.com/child_photo_1.jpg'
                ],
            }),
            200: pd.DataFrame({
                'identifier': ['uuid-1'],
                'datapoint_id': [2002],
                str(photo_question_2.pk): [
                    'https://example.com/child_photo_2.jpg'
                ],
            })
        }

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 2)
        result_pks = {q.pk for q in result}
        self.assertIn(self.photo_question.pk, result_pks)
        self.assertIn(photo_question_2.pk, result_pks)

    def test_get_photo_questions_with_empty_child_dict(self):
        """Test handling of empty child_data_dict."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.photo_question.pk): ['https://example.com/photo.jpg'],
        })

        # Empty dict
        child_data_dict = {}

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pk, self.photo_question.pk)

    def test_get_photo_questions_with_none_child_df_in_dict(self):
        """Test handling of None DataFrame in child_data_dict."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.photo_question.pk): ['https://example.com/photo.jpg'],
        })

        # Dict with None value
        child_data_dict = {
            100: None,
        }

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 1)

    def test_get_photo_questions_with_empty_child_df_in_dict(self):
        """Test handling of empty DataFrame in child_data_dict."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.photo_question.pk): ['https://example.com/photo.jpg'],
        })

        # Dict with empty DataFrame
        child_data_dict = {
            100: pd.DataFrame(),
        }

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 1)

    def test_get_photo_questions_no_photo_questions_found(self):
        """Test when no photo questions exist in DataFrames."""
        from api.v1.v1_data.management.commands.predownload_photos import (
            Command
        )

        cmd = Command()

        # DataFrame with only text question
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.text_question.pk): ['some text'],
        })

        child_data_dict = {}

        result = cmd._get_photo_questions(parent_df, child_data_dict)

        self.assertEqual(len(result), 0)


@override_settings(USE_TZ=False, TEST_ENV=True)
class PredownloadPhotosHandleTestCase(TestCase):
    """Test suite for predownload_photos handle method."""

    def setUp(self):
        """Set up test environment."""
        self.form = Forms.objects.create(
            name="Test Form",
            version=1
        )
        self.qg = QuestionGroup.objects.create(
            form=self.form,
            name="Test Group",
            order=1
        )
        self.photo_question = Questions.objects.create(
            form=self.form,
            question_group=self.qg,
            name="test_photo",
            label="Test Photo Question",
            order=1,
            type=QuestionTypes.image
        )

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.PhotoPreDownloader'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_handle_with_multi_child_dict(
        self, mock_validate, mock_get_form, mock_load_data, mock_downloader
    ):
        """Test handle method processes multi-child dict correctly."""
        mock_get_form.return_value = self.form

        # Mock load_and_prepare_data to return parent + child dict
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.photo_question.pk): ['https://example.com/photo.jpg'],
        })
        child_data_dict = {
            100: pd.DataFrame({
                'identifier': ['uuid-1'],
                'datapoint_id': [2001],
                str(self.photo_question.pk): [
                    'https://example.com/child_photo.jpg'
                ],
            })
        }
        mock_load_data.return_value = (parent_df, child_data_dict)

        # Mock downloader
        mock_downloader_instance = MagicMock()
        mock_downloader_instance.load_success_log.return_value = {}
        mock_downloader_instance.download_photos.return_value = (2, 0)
        mock_downloader_instance.get_success_log_path.return_value = '/tmp/log'
        mock_downloader.return_value = mock_downloader_instance
        mock_downloader.extract_photo_urls_with_context = MagicMock(
            return_value=[
                {'url': 'https://example.com/photo.jpg', 'datapoint_id': 1001}
            ]
        )

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            stdout=out,
            stderr=StringIO()
        )

        # Verify extract_photo_urls_with_context was called twice
        # (once for parent, once for child)
        self.assertEqual(
            mock_downloader.extract_photo_urls_with_context.call_count,
            2
        )

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_handle_no_parent_data(
        self, mock_validate, mock_get_form, mock_load_data
    ):
        """Test handle when no parent data found."""
        mock_get_form.return_value = self.form
        mock_load_data.return_value = (None, {})

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            stdout=out,
            stderr=StringIO()
        )

        output = out.getvalue()
        self.assertIn("No parent data found", output)

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_handle_empty_parent_data(
        self, mock_validate, mock_get_form, mock_load_data
    ):
        """Test handle when parent DataFrame is empty."""
        mock_get_form.return_value = self.form
        mock_load_data.return_value = (pd.DataFrame(), {})

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            stdout=out,
            stderr=StringIO()
        )

        output = out.getvalue()
        self.assertIn("No parent data found", output)

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.PhotoPreDownloader'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_handle_no_photo_questions(
        self, mock_validate, mock_get_form, mock_load_data, mock_downloader
    ):
        """Test handle when no photo questions found."""
        mock_get_form.return_value = self.form

        # DataFrame without any photo question columns
        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            'some_other_column': ['value'],
        })
        mock_load_data.return_value = (parent_df, {})

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            stdout=out,
            stderr=StringIO()
        )

        output = out.getvalue()
        self.assertIn("No photo questions found", output)

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.PhotoPreDownloader'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_handle_with_empty_child_dfs(
        self, mock_validate, mock_get_form, mock_load_data, mock_downloader
    ):
        """Test handle correctly skips empty child DataFrames."""
        mock_get_form.return_value = self.form

        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(self.photo_question.pk): ['https://example.com/photo.jpg'],
        })

        # Mix of empty and non-empty child DataFrames
        child_data_dict = {
            100: pd.DataFrame(),  # Empty
            200: None,  # None
            300: pd.DataFrame({  # Valid
                'identifier': ['uuid-1'],
                'datapoint_id': [3001],
                str(self.photo_question.pk): [
                    'https://example.com/child_photo.jpg'
                ],
            })
        }
        mock_load_data.return_value = (parent_df, child_data_dict)

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.load_success_log.return_value = {}
        mock_downloader_instance.download_photos.return_value = (2, 0)
        mock_downloader_instance.get_success_log_path.return_value = '/tmp/log'
        mock_downloader.return_value = mock_downloader_instance
        mock_downloader.extract_photo_urls_with_context = MagicMock(
            return_value=[
                {'url': 'https://example.com/photo.jpg', 'datapoint_id': 1001}
            ]
        )

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            stdout=out,
            stderr=StringIO()
        )

        # Should call extract for parent + only the valid child (form 300)
        self.assertEqual(
            mock_downloader.extract_photo_urls_with_context.call_count,
            2
        )


@override_settings(USE_TZ=False, TEST_ENV=True)
class PredownloadPhotosWorkerOptionTestCase(TestCase):
    """Test suite for workers option."""

    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.PhotoPreDownloader'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.load_and_prepare_data'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.get_form_by_flow_id'
    )
    @patch(
        'api.v1.v1_data.management.commands'
        '.predownload_photos.validate_configuration'
    )
    def test_custom_workers_option(
        self, mock_validate, mock_get_form, mock_load_data, mock_downloader
    ):
        """Test that --workers option is passed to PhotoPreDownloader."""
        form = Forms.objects.create(name="Test Form", version=1)
        qg = QuestionGroup.objects.create(
            form=form, name="Test Group", order=1
        )
        photo_q = Questions.objects.create(
            form=form,
            question_group=qg,
            name="photo",
            label="Photo",
            order=1,
            type=QuestionTypes.image
        )

        mock_get_form.return_value = form

        parent_df = pd.DataFrame({
            'identifier': ['uuid-1'],
            'datapoint_id': [1001],
            str(photo_q.pk): ['https://example.com/photo.jpg'],
        })
        mock_load_data.return_value = (parent_df, {})

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.load_success_log.return_value = {}
        mock_downloader_instance.download_photos.return_value = (1, 0)
        mock_downloader_instance.get_success_log_path.return_value = '/tmp/log'
        mock_downloader.return_value = mock_downloader_instance
        mock_downloader.extract_photo_urls_with_context = MagicMock(
            return_value=[
                {'url': 'https://example.com/photo.jpg', 'datapoint_id': 1001}
            ]
        )

        out = StringIO()
        call_command(
            "predownload_photos",
            "-f", "123",
            "--workers", "10",
            stdout=out,
            stderr=StringIO()
        )

        # Verify PhotoPreDownloader was initialized with workers=10
        mock_downloader.assert_called_once()
        call_kwargs = mock_downloader.call_args[1]
        self.assertEqual(call_kwargs['workers'], 10)
