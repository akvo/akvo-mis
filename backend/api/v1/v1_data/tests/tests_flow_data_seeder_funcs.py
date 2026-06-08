"""
Tests for Flow Data Seeder utility modules.

This module tests the utility functions that were extracted from
the flow_data_seeder command into separate modules for better
code organization and reusability.
"""

import pandas as pd
from unittest.mock import patch
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_forms.models import QuestionTypes
from utils.seeder_config import (
    CsvColumns,
    FilePaths,
    SeederConfig,
)
from utils.seeder_data_loader import load_administration_mappings
from utils.seeder_answer_processor import AnswerProcessor


@override_settings(USE_TZ=False, TEST_ENV=True)
class AnswerProcessorTestCase(TestCase):
    """Test suite for AnswerProcessor class."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.processor = AnswerProcessor()

    def test_process_administration_returns_admin_id(self):
        """Test processing administration-type questions."""
        name, value, options = self.processor.process_administration(
            row_value="some_value",
            administration_id=123
        )
        self.assertIsNone(name)
        self.assertEqual(value, 123)
        self.assertIsNone(options)

    def test_process_administration_without_admin_id(self):
        """Test processing administration without admin_id."""
        name, value, options = self.processor.process_administration(
            row_value="some_value",
            administration_id=None
        )
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_geo_with_valid_value(self):
        """Test processing geo-type questions with valid value."""
        name, value, options = self.processor.process_geo("1.0|2.0")
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertEqual(options, [1.0, 2.0])

    def test_process_geo_with_none_value(self):
        """Test processing geo-type questions with None value."""
        name, value, options = self.processor.process_geo(None)
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_option_with_valid_value(self):
        """Test processing option-type questions."""
        opt_list = ["option1", "option2", "option3"]
        name, value, options = self.processor.process_option(
            "option1|option2",
            opt_list=opt_list
        )
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertEqual(options, ["option1", "option2"])

    def test_process_option_with_invalid_value(self):
        """Test processing option-type questions with invalid value."""
        opt_list = ["option1", "option2"]
        name, value, options = self.processor.process_option(
            "invalid_option",
            opt_list=opt_list
        )
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_number_with_valid_value(self):
        """Test processing number-type questions."""
        name, value, options = self.processor.process_number("123.45")
        self.assertIsNone(name)
        self.assertEqual(value, 123.45)
        self.assertIsNone(options)

    def test_process_number_with_invalid_value(self):
        """Test processing number-type questions with invalid value."""
        name, value, options = self.processor.process_number("not_a_number")
        self.assertIsNone(name)
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_default_with_string(self):
        """Test processing default question types."""
        name, value, options = self.processor.process_default("test value")
        self.assertEqual(name, "test value")
        self.assertIsNone(value)
        self.assertIsNone(options)

    def test_process_with_question_type_administration(self):
        """Test process method with administration question type."""
        name, value, options = self.processor.process(
            question_type=QuestionTypes.cascade,
            row_value="some_value",
            administration_id=123
        )
        self.assertIsNone(name)
        self.assertEqual(value, 123)

    def test_process_with_question_type_geo(self):
        """Test process method with geo question type."""
        name, value, options = self.processor.process(
            question_type=QuestionTypes.geo,
            row_value="1.0|2.0"
        )
        self.assertEqual(options, [1.0, 2.0])

    def test_process_with_question_type_option(self):
        """Test process method with option question type."""
        name, value, options = self.processor.process(
            question_type=QuestionTypes.option,
            row_value="option1",
            opt_list=["option1", "option2"]
        )
        self.assertEqual(options, ["option1"])

    def test_process_with_question_type_number(self):
        """Test process method with number question type."""
        name, value, options = self.processor.process(
            question_type=QuestionTypes.number,
            row_value="42.5"
        )
        self.assertEqual(value, 42.5)

    def test_process_with_unknown_question_type(self):
        """Test process method with unknown question type."""
        name, value, options = self.processor.process(
            question_type="unknown_type",
            row_value="test value"
        )
        self.assertEqual(name, "test value")


@override_settings(USE_TZ=False, TEST_ENV=True)
class LoadAdministrationMappingsTestCase(TestCase):
    """Test suite for load_administration_mappings function."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.config = SeederConfig(flow_form_id=123)

    @patch('pandas.read_csv')
    def test_load_administration_mappings_success(self, mock_read_csv):
        """Test successful loading of administration mappings."""
        csv_data = pd.DataFrame({
            'flow_datapoint_id': [1, 2, 3],
            'mis_value': ['adm1', 'adm2', 'adm3'],
        })
        mock_read_csv.return_value = csv_data

        result = load_administration_mappings(self.config)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[1], 'adm1')
        self.assertEqual(result[2], 'adm2')
        self.assertEqual(result[3], 'adm3')

    @patch('pandas.read_csv')
    def test_load_administration_mappings_filters_empty_values(
        self, mock_read_csv
    ):
        """Test that empty and null mis_value are filtered out."""
        csv_data = pd.DataFrame({
            'flow_datapoint_id': [1, 2, 3, 4],
            'mis_value': ['adm1', '', None, 'adm3'],
        })
        mock_read_csv.return_value = csv_data

        result = load_administration_mappings(self.config)

        self.assertEqual(len(result), 2)
        self.assertIn(1, result)
        self.assertIn(4, result)
        self.assertNotIn(2, result)
        self.assertNotIn(3, result)

    @patch('pandas.read_csv')
    def test_load_administration_mappings_file_not_found(
        self, mock_read_csv
    ):
        """Test handling when file is not found."""
        mock_read_csv.side_effect = FileNotFoundError("File not found")

        result = load_administration_mappings(self.config)

        self.assertEqual(result, {})

    @patch('pandas.read_csv')
    def test_load_administration_mappings_empty_file(self, mock_read_csv):
        """Test handling when file is empty."""
        mock_read_csv.side_effect = pd.errors.EmptyDataError("Empty file")

        result = load_administration_mappings(self.config)

        self.assertEqual(result, {})

    @patch('pandas.read_csv')
    def test_load_administration_mappings_missing_columns(
        self, mock_read_csv
    ):
        """Test handling when CSV has missing columns."""
        mock_read_csv.side_effect = KeyError("Missing columns")

        with self.assertRaises(Exception):
            load_administration_mappings(self.config)


@override_settings(USE_TZ=False, TEST_ENV=True)
class SeederConfigTestCase(TestCase):
    """Test suite for SeederConfig."""

    def test_seeder_config_creation(self):
        """Test creating a SeederConfig instance."""
        config = SeederConfig(
            flow_form_id=123,
            limit=100,
        )
        self.assertEqual(config.flow_form_id, 123)
        self.assertEqual(config.limit, 100)

    def test_seeder_config_defaults(self):
        """Test SeederConfig default values."""
        config = SeederConfig(flow_form_id=123)
        self.assertEqual(config.flow_form_id, 123)
        self.assertIsNone(config.limit)
        self.assertIsNone(config.user)
        self.assertEqual(config.batch_size, 1000)
        self.assertEqual(config.encoding, "utf-8")


@override_settings(USE_TZ=False, TEST_ENV=True)
class CsvColumnsTestCase(TestCase):
    """Test suite for CsvColumns constants."""

    def test_datapoint_id_column(self):
        """Test DATAPOINT_ID constant."""
        self.assertEqual(CsvColumns.DATAPOINT_ID, "datapoint_id")

    def test_name_column(self):
        """Test NAME constant."""
        self.assertEqual(CsvColumns.NAME, "name")

    def test_submitter_column(self):
        """Test SUBMITTER constant."""
        self.assertEqual(CsvColumns.SUBMITTER, "submitter")

    def test_identifier_column(self):
        """Test IDENTIFIER constant."""
        self.assertEqual(CsvColumns.IDENTIFIER, "identifier")

    def test_created_at_column(self):
        """Test CREATED_AT constant."""
        self.assertEqual(CsvColumns.CREATED_AT, "created_at")

    def test_form_id_column(self):
        """Test FORM_ID constant."""
        self.assertEqual(CsvColumns.FORM_ID, "form_id")

    def test_administration_column(self):
        """Test ADMINISTRATION constant."""
        self.assertEqual(CsvColumns.ADMINISTRATION, "administration")

    def test_geo_column(self):
        """Test GEO constant."""
        self.assertEqual(CsvColumns.GEO, "geo")


@override_settings(USE_TZ=False, TEST_ENV=True)
class FilePathsTestCase(TestCase):
    """Test suite for FilePaths constants."""

    def test_output_dir(self):
        """Test OUTPUT_DIR constant."""
        self.assertEqual(FilePaths.OUTPUT_DIR, "data")

    def test_source_dir(self):
        """Test SOURCE_DIR constant."""
        self.assertEqual(FilePaths.SOURCE_DIR, "storage/akvo-flow")

    def test_administration_mapping(self):
        """Test ADMINISTRATION_MAPPING constant."""
        self.assertEqual(
            FilePaths.ADMINISTRATION_MAPPING,
            "administration_mapping.csv"
        )
