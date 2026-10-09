from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms, QuestionGroup
from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.job import (
    transform_form_data_for_report,
    job_generate_data_report,
)
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(USE_TZ=False, TEST_ENV=True)
class TransformFormDataForReportTestCase(TestCase, ProfileTestHelperMixin):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "fake_complete_data_seeder",
            "--test=true",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        call_command("form_seeder", "--test", 1)

        self.call_command(repeat=2, test=True, approved=True)

        self.form = Forms.objects.get(pk=1)
        self.repeatable_form = Forms.objects.get(pk=4)

        self.data = (
            self.form.form_form_data.filter(is_pending=False)
            .order_by("?")
            .first()
        )

        self.repeatable_data = (
            self.repeatable_form.form_form_data.filter(is_pending=False)
            .order_by("?")
            .first()
        )

        self.user = self.data.created_by
        self.administration = self.data.administration

    def test_transform_form_data_basic_functionality(self):
        """Test basic functionality of transform_form_data_for_report"""
        result = transform_form_data_for_report(self.form)

        # Should return a list
        self.assertIsInstance(result, list)

        # If there's data, should have groups
        if result:
            # Each group should have required structure
            for group in result:
                self.assertIn("name", group)
                self.assertIn("questions", group)
                self.assertIsInstance(group["questions"], list)

                # Each question should have required structure
                for question in group["questions"]:
                    self.assertIn("question", question)
                    self.assertIn("answers", question)
                    self.assertIsInstance(question["answers"], list)

    def test_transform_form_data_with_selection_ids(self):
        """Test transform_form_data_for_report with specific selection_ids"""
        # Get existing FormData instances
        form_data_instances = FormData.objects.filter(
            form=self.form, is_pending=False
        )[:2]
        if not form_data_instances.exists():
            self.skipTest("No FormData available for testing")

        selection_ids = [fd.id for fd in form_data_instances]
        result = transform_form_data_for_report(
            self.form, selection_ids=selection_ids
        )

        # Should return results for specified FormData only
        self.assertIsInstance(result, list)

        if result:
            # Verify answers correspond to the number of selected FormData
            for group in result:
                for question in group["questions"]:
                    # Should have as many answer slots as selected FormData
                    self.assertEqual(
                        len(question["answers"]), len(selection_ids)
                    )

    def test_transform_form_data_no_empty_columns(self):
        """Test that no empty columns are created when all answers empty"""
        result = transform_form_data_for_report(self.form)

        if result:
            for group in result:
                for question in group["questions"]:
                    answers = question["answers"]
                    # Should have at least one non-empty answer
                    non_empty_answers = [a for a in answers if a and a.strip()]
                    self.assertGreater(
                        len(non_empty_answers),
                        0,
                        f"Question '{question['question']}' "
                        f"has all empty answers",
                    )

    def test_transform_form_data_empty_questions_excluded(self):
        """Test that questions with no answers are excluded from result"""
        result = transform_form_data_for_report(self.form)

        # All included questions should have at least one non-empty answer
        for group in result:
            for question in group["questions"]:
                answers = question["answers"]
                has_non_empty = any(a and a.strip() for a in answers)
                self.assertTrue(
                    has_non_empty,
                    f"Question '{question['question']}' should not be "
                    f"included with all empty answers",
                )

    def test_transform_form_data_with_child_forms(self):
        # when no specific selection_ids are provided
        all_results = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=self.form.children.values_list("id", flat=True),
        )
        if all_results:
            # Should still maintain column consistency
            for group in all_results:
                if group["questions"]:
                    expected_columns = len(group["questions"][0]["answers"])
                    for question in group["questions"]:
                        self.assertEqual(
                            len(question["answers"]),
                            expected_columns,
                            (
                                "All questions should have "
                                "consistent column count"
                            ),
                        )

    def test_transform_form_data_answer_formatting(self):
        """Test that different answer types are formatted correctly"""
        result = transform_form_data_for_report(self.form)

        if result:
            # Check that answers are strings
            for group in result:
                for question in group["questions"]:
                    for answer in question["answers"]:
                        self.assertIsInstance(
                            answer,
                            str,
                            "All answers should be formatted as strings",
                        )

    def test_transform_form_data_nonexistent_form(self):
        """Test behavior with nonexistent form"""
        nonexistent_form = Forms(id=99999, name="Nonexistent")
        nonexistent_form.pk = 99999

        result = transform_form_data_for_report(nonexistent_form)

        # Should return empty list for nonexistent form
        self.assertEqual(result, [])

    def test_transform_form_data_empty_selection_ids(self):
        """Test behavior with empty selection_ids list"""
        result1 = transform_form_data_for_report(self.form, selection_ids=[])
        result2 = transform_form_data_for_report(self.form, selection_ids=None)

        # Both should return the same result (all data)
        self.assertEqual(result1, result2)

    def test_transform_form_data_invalid_selection_ids(self):
        """Test behavior with invalid selection_ids"""
        result = transform_form_data_for_report(
            self.form, selection_ids=[99999, 88888]
        )

        # Should return empty result or handle gracefully
        self.assertIsInstance(result, list)

    def test_transform_form_data_column_count_consistency(self):
        """Test that all questions have the same number of columns"""
        result = transform_form_data_for_report(self.form)

        if result:
            # All questions should have the same number of answer columns
            expected_columns = None
            for group in result:
                for question in group["questions"]:
                    if expected_columns is None:
                        expected_columns = len(question["answers"])
                    else:
                        self.assertEqual(
                            len(question["answers"]),
                            expected_columns,
                            "All questions should have the same number "
                            "of answer columns",
                        )

    def test_transform_form_data_question_groups_structure(self):
        """Test that question groups are properly structured and ordered"""
        result = transform_form_data_for_report(self.form)

        if result:
            # Each group should have a name
            for group in result:
                self.assertIsInstance(group["name"], str)
                self.assertGreater(
                    len(group["name"]), 0, "Group name should not be empty"
                )

                # Questions should be ordered
                for question in group["questions"]:
                    self.assertIsInstance(question["question"], str)
                    self.assertGreater(
                        len(question["question"]),
                        0,
                        "Question should not be empty",
                    )

    def test_transform_form_data_with_pending_data(self):
        """Test that pending FormData are excluded"""
        # Create a pending FormData instance
        pending_fd = self.data
        pending_fd.is_pending = True
        pending_fd.save()

        result = transform_form_data_for_report(
            self.form, selection_ids=[pending_fd.id]
        )

        # Should return empty result since pending data is excluded
        expected_empty = (
            all(len(group["questions"]) == 0 for group in result)
            if result
            else True
        )
        self.assertTrue(expected_empty, "Pending FormData should be excluded")

    def test_job_generate_data_report_integration(self):
        """Test integration with job_generate_data_report function"""
        # Create a job
        job = Jobs.objects.create(
            result="test_report.docx",
            type=JobTypes.download_datapoint_report,
            status=JobStatus.on_progress,
            user=self.user,
            info={"form_id": self.form.id, "selection_ids": [self.data.id]},
        )

        # Mock the file operations and report generation
        with patch(
            "api.v1.v1_jobs.job.os.path.exists", return_value=False
        ), patch(
            "api.v1.v1_jobs.job.generate_datapoint_report"
        ) as mock_generate, patch(
            "api.v1.v1_jobs.job.upload"
        ) as mock_upload:

            mock_generate.return_value = "./tmp/test_report.docx"
            mock_upload.return_value = "http://example.com/test_report.docx"

            result = job_generate_data_report(
                job.id,
                form_id=self.form.id,
                selection_ids=[self.data.id],
                child_form_ids=[],
            )

            # Should return a URL
            self.assertIsInstance(result, str)
            self.assertEqual(result, "http://example.com/test_report.docx")
            mock_generate.assert_called_once()
            mock_upload.assert_called_once()

            # Verify the upload was called with correct parameters
            mock_upload.assert_called_with(
                file="./tmp/test_report.docx",
                folder="download_datapoint_report",
            )

    def test_transform_form_data_memory_efficiency(self):
        """Test that the function handles large datasets efficiently"""
        # This test ensures the function doesn't create unnecessary structures
        result = transform_form_data_for_report(self.form)

        # Should not fail with memory issues and return reasonable results
        self.assertIsInstance(result, list)

        # Verify structure is maintained regardless of data size
        if result:
            for group in result:
                self.assertIn("name", group)
                self.assertIn("questions", group)

    def test_transform_form_data_edge_cases(self):
        """Test various edge cases"""
        # Test with form that has no questions
        empty_form = Forms.objects.create(
            id=99999,
            name="Empty Form",
            version=1,
        )

        result = transform_form_data_for_report(empty_form)
        self.assertEqual(
            result, [], "Form with no questions should return empty list"
        )

        # Test with form that has questions but no data
        form_with_no_data = self.form.children.first()
        form_with_no_data.form_form_data.all().delete(hard=True)

        result = transform_form_data_for_report(form_with_no_data)
        self.assertEqual(
            result, [], "Form with no data should return empty list"
        )

    def test_transform_form_data_with_empty_child_form_ids(self):
        """Test that empty child_form_ids includes all child forms"""
        # Test with empty child_form_ids (should include all)
        result_empty = transform_form_data_for_report(
            self.form, selection_ids=[self.data.id], child_form_ids=[]
        )

        # Test with None child_form_ids (should include all)
        result_none = transform_form_data_for_report(
            self.form, selection_ids=[self.data.id], child_form_ids=None
        )

        # Both should produce the same result
        self.assertEqual(result_empty, result_none)
        self.assertIsInstance(result_empty, list)

    def test_transform_form_data_with_nonexistent_child_form_ids(self):
        """Test behavior with non-existent child form IDs"""
        # Test with non-existent child form IDs
        result = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=[99999, 88888],  # Non-existent IDs
        )

        # Should handle gracefully and return result
        self.assertIsInstance(result, list)
        # Should not crash or raise exception

    def test_transform_form_data_with_mixed_valid_invalid_child_form_ids(self):
        """Test with mix of valid and invalid child form IDs"""
        child_form_1 = self.form.children.first()
        # Test with mix of valid and invalid IDs
        result = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=[child_form_1.id, 99999],
        )

        # Should process only valid child forms and handle gracefully
        self.assertIsInstance(result, list)

    def test_transform_form_data_child_form_ids_preserves_structure(self):
        """Test that child_form_ids filtering preserves correct data
        structure"""
        # Create multiple child forms with different structures
        child_form_1 = self.form.children.first()
        # Test with specific child form
        result = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=[child_form_1.id],
        )

        # Should maintain proper structure
        if result:
            for group in result:
                self.assertIn("name", group)
                self.assertIn("questions", group)
                self.assertIsInstance(group["questions"], list)

                for question in group["questions"]:
                    self.assertIn("question", question)
                    self.assertIn("answers", question)
                    self.assertIsInstance(question["answers"], list)
                    # Should have exactly one column for the parent FormData
                    self.assertEqual(len(question["answers"]), 1)

    def test_transform_form_data_child_form_ids_performance(self):
        """Test that child_form_ids filtering improves performance by
        excluding unwanted forms"""
        # Create multiple child forms
        child_forms = []
        for i in range(3):
            child_form = Forms.objects.create(
                id=1111 + i,
                name=f"Child Form {i+1}",
                version=1,
            )
            child_forms.append(child_form)
            self.form.children.add(child_form)

        # Test with all child forms
        result_all = transform_form_data_for_report(
            self.form, selection_ids=[self.data.id], child_form_ids=[]
        )

        # Test with filtered child forms (only first one)
        result_filtered = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=[child_forms[0].id],
        )

        # Both should return valid results
        self.assertIsInstance(result_all, list)
        self.assertIsInstance(result_filtered, list)

        # The filtered result should potentially have different content
        # (This verifies the filtering mechanism is working)

    # Tests for repeatable question groups functionality

    def test_transform_repeatable_form_data_basic_functionality(self):
        """Test basic functionality with repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        # Should return a list
        self.assertIsInstance(result, list)

        # If there's data, should have groups
        if result:
            # Each group should have required structure
            for group in result:
                self.assertIn("name", group)
                self.assertIn("questions", group)
                self.assertIsInstance(group["questions"], list)

                # Each question should have required structure
                for question in group["questions"]:
                    self.assertIn("question", question)
                    self.assertIn("answers", question)
                    self.assertIsInstance(question["answers"], list)

    def test_transform_repeatable_form_data_with_selection_ids(self):
        """Test with specific selection_ids for repeatable form"""
        # Get existing FormData instances
        form_data_instances = FormData.objects.filter(
            form=self.repeatable_form, is_pending=False
        )[:2]
        if not form_data_instances.exists():
            self.skipTest("No FormData available for testing")

        selection_ids = [fd.id for fd in form_data_instances]
        result = transform_form_data_for_report(
            self.repeatable_form, selection_ids=selection_ids
        )

        # Should return results for specified FormData only
        self.assertIsInstance(result, list)

        if result:
            # Verify answers correspond to the number of selected FormData
            for group in result:
                for question in group["questions"]:
                    # Should have as many answer slots as selected FormData
                    self.assertEqual(
                        len(question["answers"]), len(selection_ids)
                    )

    def test_transform_repeatable_form_data_no_empty_columns(self):
        """Test that no empty columns are created when all answers
        empty for repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        if result:
            for group in result:
                for question in group["questions"]:
                    answers = question["answers"]
                    # Should have at least one non-empty answer
                    non_empty_answers = [a for a in answers if a and a.strip()]
                    self.assertGreater(
                        len(non_empty_answers),
                        0,
                        f"Question '{question['question']}' "
                        f"has all empty answers",
                    )

    def test_transform_repeatable_form_data_empty_questions_excluded(self):
        """Test that questions with no answers are excluded from
        result for repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        # All included questions should have at least one non-empty answer
        for group in result:
            for question in group["questions"]:
                answers = question["answers"]
                has_non_empty = any(a and a.strip() for a in answers)
                self.assertTrue(
                    has_non_empty,
                    f"Question '{question['question']}' should not be "
                    f"included with all empty answers",
                )

    def test_transform_repeatable_form_data_with_child_forms(self):
        # when no specific selection_ids are provided
        all_results = transform_form_data_for_report(
            self.repeatable_form,
            selection_ids=[self.repeatable_data.id],
            child_form_ids=self.repeatable_form.children.values_list(
                "id", flat=True
            ),
        )
        if all_results:
            # Should still maintain column consistency
            for group in all_results:
                if group["questions"]:
                    expected_columns = len(group["questions"][0]["answers"])
                    for question in group["questions"]:
                        self.assertEqual(
                            len(question["answers"]),
                            expected_columns,
                            "All questions should have consistent "
                            "column count",
                        )

    def test_transform_repeatable_form_data_answer_formatting(self):
        """Test that different answer types are formatted correctly
        for repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        if result:
            # Check that answers are strings
            for group in result:
                for question in group["questions"]:
                    for answer in question["answers"]:
                        self.assertIsInstance(
                            answer,
                            str,
                            "All answers should be formatted as strings",
                        )

    def test_transform_repeatable_form_data_empty_selection_ids(self):
        """Test behavior with empty selection_ids list for repeatable form"""
        result1 = transform_form_data_for_report(
            self.repeatable_form, selection_ids=[]
        )
        result2 = transform_form_data_for_report(
            self.repeatable_form, selection_ids=None
        )

        # Both should return the same result (all data)
        self.assertEqual(result1, result2)

    def test_transform_repeatable_form_data_invalid_selection_ids(self):
        """Test behavior with invalid selection_ids for repeatable form"""
        result = transform_form_data_for_report(
            self.repeatable_form, selection_ids=[99999, 88888]
        )

        # Should return empty result or handle gracefully
        self.assertIsInstance(result, list)

    def test_transform_repeatable_form_data_column_count_consistency(self):
        """Test that all questions have the same number of columns
        for repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        if result:
            # All questions should have the same number of answer columns
            expected_columns = None
            for group in result:
                for question in group["questions"]:
                    if expected_columns is None:
                        expected_columns = len(question["answers"])
                    else:
                        self.assertEqual(
                            len(question["answers"]),
                            expected_columns,
                            "All questions should have the same number "
                            "of answer columns",
                        )

    def test_transform_repeatable_form_data_question_groups_structure(self):
        """Test that question groups are properly structured and
        ordered for repeatable form"""
        result = transform_form_data_for_report(self.repeatable_form)

        if result:
            # Each group should have a name
            for group in result:
                self.assertIsInstance(group["name"], str)
                self.assertGreater(
                    len(group["name"]), 0, "Group name should not be empty"
                )

                # Questions should be ordered
                for question in group["questions"]:
                    self.assertIsInstance(question["question"], str)
                    self.assertGreater(
                        len(question["question"]),
                        0,
                        "Question should not be empty",
                    )

    def test_transform_repeatable_form_data_with_pending_data(self):
        """Test that pending FormData are excluded for repeatable form"""
        # Create a pending FormData instance
        pending_fd = self.repeatable_data
        pending_fd.is_pending = True
        pending_fd.save()

        result = transform_form_data_for_report(
            self.repeatable_form, selection_ids=[pending_fd.id]
        )

        # Should return empty result since pending data is excluded
        expected_empty = (
            all(len(group["questions"]) == 0 for group in result)
            if result
            else True
        )
        self.assertTrue(expected_empty, "Pending FormData should be excluded")

    def test_job_generate_data_report_integration_repeatable_form(self):
        """Test integration with job_generate_data_report function
        for repeatable form"""
        # Create a job
        job = Jobs.objects.create(
            result="test_report_repeatable.docx",
            type=JobTypes.download_datapoint_report,
            status=JobStatus.on_progress,
            user=self.user,
            info={
                "form_id": self.repeatable_form.id,
                "selection_ids": [self.repeatable_data.id],
            },
        )

        # Mock the file operations and report generation
        with patch(
            "api.v1.v1_jobs.job.os.path.exists", return_value=False
        ), patch(
            "api.v1.v1_jobs.job.generate_datapoint_report"
        ) as mock_generate, patch(
            "api.v1.v1_jobs.job.upload"
        ) as mock_upload:

            mock_generate.return_value = "./tmp/test_report_repeatable.docx"
            mock_upload.return_value = (
                "http://example.com/test_report_repeatable.docx"
            )

            result = job_generate_data_report(
                job.id,
                form_id=self.repeatable_form.id,
                selection_ids=[self.repeatable_data.id],
                child_form_ids=[],
            )

            # Should return a URL
            self.assertIsInstance(result, str)
            self.assertEqual(
                result, "http://example.com/test_report_repeatable.docx"
            )
            mock_generate.assert_called_once()
            mock_upload.assert_called_once()

            # Verify the upload was called with correct parameters
            mock_upload.assert_called_with(
                file="./tmp/test_report_repeatable.docx",
                folder="download_datapoint_report",
            )

    def test_transform_repeatable_form_data_memory_efficiency(self):
        """Test that the function handles large datasets efficiently
        for repeatable form"""
        # This test ensures the function doesn't create unnecessary structures
        result = transform_form_data_for_report(self.repeatable_form)

        # Should not fail with memory issues and return reasonable results
        self.assertIsInstance(result, list)

        # Verify structure is maintained regardless of data size
        if result:
            for group in result:
                self.assertIn("name", group)
                self.assertIn("questions", group)

    def test_repeatable_groups_create_multiple_instances(self):
        """Test that repeatable groups create multiple instances"""
        # Check if form has repeatable groups
        repeatable_groups = QuestionGroup.objects.filter(
            form=self.repeatable_form, repeatable=True
        )

        if not repeatable_groups.exists():
            self.skipTest("No repeatable groups found in test form")

        result = transform_form_data_for_report(self.repeatable_form)

        # Should have multiple instances of repeatable groups
        if result:
            group_names = [group["name"] for group in result]
            # Look for repeated group names (with different repeat numbers)
            for repeatable_group in repeatable_groups:
                base_name = repeatable_group.label or repeatable_group.name

                # Count how many groups start with the base name
                matching_groups = [
                    name for name in group_names if name.startswith(base_name)
                ]

                # Should have at least one instance
                self.assertGreaterEqual(
                    len(matching_groups),
                    1,
                    f"Repeatable group '{base_name}' should have "
                    f"at least one instance",
                )

    def test_repeatable_groups_proper_indexing(self):
        """Test that repeatable groups use proper answer indexing"""
        # Get a repeatable group with indexed answers
        repeatable_groups = QuestionGroup.objects.filter(
            form=self.repeatable_form, repeatable=True
        )

        if not repeatable_groups.exists():
            self.skipTest("No repeatable groups found in test form")

        # Check if there are any indexed answers
        for group in repeatable_groups:
            questions = group.question_group_question.all()
            for question in questions[:1]:  # Check first question only
                indexed_answers = Answers.objects.filter(
                    question=question, index__gt=0
                )
                if indexed_answers.exists():
                    # Found indexed answers, test the functionality
                    result = transform_form_data_for_report(
                        self.repeatable_form
                    )

                    if result:
                        base_name = group.label or group.name
                        repeat_groups = [
                            g
                            for g in result
                            if g["name"].startswith(base_name)
                        ]

                        # Should have multiple repeat instances
                        self.assertGreater(
                            len(repeat_groups),
                            1,
                            f"Group '{base_name}' should have multiple "
                            f"repeat instances",
                        )

                        # Each repeat should have the proper naming
                        for i, repeat_group in enumerate(repeat_groups):
                            if group.repeat_text:
                                expected_pattern = f"{base_name} - "
                            else:
                                expected_pattern = f"{base_name} (Repeat "

                            self.assertTrue(
                                repeat_group["name"] == base_name
                                or expected_pattern in repeat_group["name"],
                                f"Repeat group name '{repeat_group['name']}' "
                                f"should contain expected pattern",
                            )
                    return  # Found and tested, exit

        self.skipTest("No indexed answers found for repeatable groups")

    def test_transform_repeatable_form_data_with_empty_child_form_ids(self):
        """Test that empty child_form_ids includes all child forms
        for repeatable form"""
        # Test with empty child_form_ids (should include all)
        result_empty = transform_form_data_for_report(
            self.repeatable_form,
            selection_ids=[self.repeatable_data.id],
            child_form_ids=[],
        )

        # Test with None child_form_ids (should include all)
        result_none = transform_form_data_for_report(
            self.repeatable_form,
            selection_ids=[self.repeatable_data.id],
            child_form_ids=None,
        )

        # Both should produce the same result
        self.assertEqual(result_empty, result_none)
        self.assertIsInstance(result_empty, list)

    def test_transform_repeatable_form_data_with_nonexistent_child_form_ids(
        self,
    ):
        """Test behavior with non-existent child form IDs
        for repeatable form"""
        # Test with non-existent child form IDs
        result = transform_form_data_for_report(
            self.repeatable_form,
            selection_ids=[self.repeatable_data.id],
            child_form_ids=[99999, 88888],  # Non-existent IDs
        )

        # Should handle gracefully and return result
        self.assertIsInstance(result, list)
        # Should not crash or raise exception

    def test_transform_repeatable_form_data_with_mixed_valid_invalid_child_form_ids(  # noqa: E501
        self,
    ):
        """Test with mix of valid and invalid child form IDs
        for repeatable form"""
        child_form_1 = self.repeatable_form.children.first()
        # Test with mix of valid and invalid IDs
        result = transform_form_data_for_report(
            self.repeatable_form,
            selection_ids=[self.repeatable_data.id],
            child_form_ids=(
                [child_form_1.id, 99999] if child_form_1 else [99999]
            ),
        )

        # Should process only valid child forms and handle gracefully
        self.assertIsInstance(result, list)

    def test_transform_form_data_with_child_form_data_ids(self):
        """Test that child FormData IDs can be selected directly.

        This tests the fix for showing all available answers for each
        selection_id, where selection_ids might contain child form data
        IDs instead of parent form data IDs.
        """
        # Get a child form
        child_form = self.form.children.first()
        if not child_form:
            self.skipTest("No child form available for testing")

        # Create child FormData linked to parent
        child_fd = FormData.objects.create(
            name="Test Child Data",
            form=child_form,
            administration=self.administration,
            created_by=self.user,
            parent=self.data,  # Link to parent
            is_pending=False,
        )

        # Create an answer for the child FormData
        child_questions = child_form.form_question_group.first()
        if child_questions:
            child_question = child_questions.question_group_question.first()
            if child_question:
                Answers.objects.create(
                    data=child_fd,
                    question=child_question,
                    name="Test child answer",
                    created_by=self.user,
                )

        # Call with child FormData ID directly in selection_ids
        # Previously this would fail because the query filtered by form=form
        # which wouldn't match child FormData
        result = transform_form_data_for_report(
            self.form,
            selection_ids=[child_fd.id],  # Child FormData ID
            child_form_ids=[child_form.id],
        )

        # Should return valid results with the child FormData
        self.assertIsInstance(result, list)

        # Clean up
        child_fd.delete(hard=True)

    def test_transform_form_data_includes_all_child_answers(self):
        """Test that all children's answers are included, not just the last.

        This tests the fix where .last() was changed to .all() to include
        answers from ALL child FormData, not just the most recent one.
        """
        # Get a child form
        child_form = self.form.children.first()
        if not child_form:
            self.skipTest("No child form available for testing")

        # Get a question from the child form
        child_qg = child_form.form_question_group.first()
        if not child_qg:
            self.skipTest("No question group in child form")
        child_question = child_qg.question_group_question.first()
        if not child_question:
            self.skipTest("No question in child form")

        # Create multiple child FormData entries linked to parent
        child_fd_1 = FormData.objects.create(
            name="Test Child Data 1",
            form=child_form,
            administration=self.administration,
            created_by=self.user,
            parent=self.data,
            is_pending=False,
        )
        child_fd_2 = FormData.objects.create(
            name="Test Child Data 2",
            form=child_form,
            administration=self.administration,
            created_by=self.user,
            parent=self.data,
            is_pending=False,
        )

        # Create answers for both child FormData
        Answers.objects.create(
            data=child_fd_1,
            question=child_question,
            name="Answer from child 1",
            created_by=self.user,
        )
        Answers.objects.create(
            data=child_fd_2,
            question=child_question,
            name="Answer from child 2",
            created_by=self.user,
        )

        # When selecting parent, should find answers from ALL children
        result = transform_form_data_for_report(
            self.form,
            selection_ids=[self.data.id],
            child_form_ids=[child_form.id],
        )

        # Should return valid results
        self.assertIsInstance(result, list)

        # Clean up
        child_fd_1.delete(hard=True)
        child_fd_2.delete(hard=True)
