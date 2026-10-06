import os
import pandas as pd
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_data.models import FormData, Answers
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import (
    Forms,
    QuestionGroup,
    Questions,
    QuestionOptions,
)
from api.v1.v1_jobs.job import (
    generate_data_sheet,
    generate_monitoring_data_sheet,
    get_answer_label,
    _resolve_base_question_name,
)
from api.v1.v1_jobs.constants import DataDownloadTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from utils.export_form import meta_columns, monitoring_meta_columns


@override_settings(USE_TZ=False)
class ExportQuestionOrderTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test", 1)
        call_command("default_roles_seeder", "--test", 1)
        self.administration = (
            Administration.objects.filter(level__level=1)
            .order_by("id")
            .first()
        )
        self.user = self.create_user(
            email="admin@akvo.org",
            password="Test105*",
            role_level=self.IS_ADMIN,
            administration=self.administration,
        )

    def test_generate_data_sheet_respects_interleaved_option_question_order(
        self,
    ):
        """
        Verify that option-type questions in the middle of a form are NOT
        displaced to the end of the sheet when use_label=True (JOB-502).
        """
        form = Forms.objects.create(
            name="Interleaved Form",
            created_by=self.user,
        )
        qg = QuestionGroup.objects.create(
            form=form,
            name="General Info",
            order=1,
        )
        # Sequence: text, option, text, option, text
        q1 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="applicant_name",
            label="Applicant Name",
            type=QuestionTypes.input,
            order=1,
        )
        q2 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="gender",
            label="Gender",
            type=QuestionTypes.option,
            order=2,
        )
        QuestionOptions.objects.create(
            question=q2, value="1", label="Male", order=1
        )
        QuestionOptions.objects.create(
            question=q2, value="2", label="Female", order=2
        )

        q3 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="home_address",
            label="Home Address",
            type=QuestionTypes.text,
            order=3,
        )
        q4 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="employment_status",
            label="Employment Status",
            type=QuestionTypes.option,
            order=4,
        )
        QuestionOptions.objects.create(
            question=q4, value="1", label="Employed", order=1
        )
        QuestionOptions.objects.create(
            question=q4, value="2", label="Unemployed", order=2
        )

        q5 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="comments",
            label="Comments",
            type=QuestionTypes.text,
            order=5,
        )

        # Create FormData directly
        fd = FormData.objects.create(
            form=form,
            name="Applicant 1",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=fd, question=q1, name="Jane Doe", created_by=self.user
        )
        Answers.objects.create(
            data=fd, question=q2, options=["2"], created_by=self.user
        )
        Answers.objects.create(
            data=fd, question=q3, name="123 Main St", created_by=self.user
        )
        Answers.objects.create(
            data=fd, question=q4, options=["1"], created_by=self.user
        )
        Answers.objects.create(
            data=fd, question=q5, name="All good", created_by=self.user
        )

        # Generate data sheet to Excel
        test_file = "./tmp/test_interleaved_order.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        df = pd.read_excel(test_file, sheet_name="data")
        expected_question_cols = [
            "applicant_name",
            "gender",
            "home_address",
            "employment_status",
            "comments",
        ]
        expected_columns = meta_columns + expected_question_cols
        self.assertEqual(list(df.columns), expected_columns)
        self.assertEqual(df["gender"].iloc[0], "Female")
        self.assertEqual(df["employment_status"].iloc[0], "Employed")

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_generate_data_sheet_preserves_unanswered_question_order(self):
        """
        Verify that unanswered questions remain at their schema position
        rather than shifting to the end of the sheet (JOB-502).
        """
        form = Forms.objects.create(
            name="Partial Form",
            created_by=self.user,
        )
        qg1 = QuestionGroup.objects.create(form=form, name="Group 1", order=1)
        qg2 = QuestionGroup.objects.create(form=form, name="Group 2", order=2)

        q1 = Questions.objects.create(
            form=form,
            question_group=qg1,
            name="first_name",
            type=QuestionTypes.input,
            order=1,
        )
        Questions.objects.create(
            form=form,
            question_group=qg1,
            name="middle_name",
            type=QuestionTypes.input,
            order=2,
        )
        q3 = Questions.objects.create(
            form=form,
            question_group=qg2,
            name="last_name",
            type=QuestionTypes.input,
            order=1,
        )
        Questions.objects.create(
            form=form,
            question_group=qg2,
            name="suffix",
            type=QuestionTypes.input,
            order=2,
        )

        # Only answer q1 and q3 (leave q2 and q4 empty)
        fd = FormData.objects.create(
            form=form,
            name="Partial Submitter",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=fd, question=q1, name="John", created_by=self.user
        )
        Answers.objects.create(
            data=fd, question=q3, name="Smith", created_by=self.user
        )

        test_file = "./tmp/test_unanswered_order.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        df = pd.read_excel(test_file, sheet_name="data")
        expected_columns = meta_columns + [
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
        ]
        self.assertEqual(list(df.columns), expected_columns)

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_generate_monitoring_data_sheet_respects_question_order(self):
        """
        Verify that monitoring export sheet respects question order when
        option questions exist in the child form.
        """
        parent_form = Forms.objects.create(
            name="Parent Facility Form",
            created_by=self.user,
        )
        parent_qg = QuestionGroup.objects.create(
            form=parent_form, name="Facility", order=1
        )
        pq1 = Questions.objects.create(
            form=parent_form,
            question_group=parent_qg,
            name="facility_name",
            type=QuestionTypes.input,
            order=1,
        )

        child_form = Forms.objects.create(
            name="Monitoring Visit",
            parent=parent_form,
            created_by=self.user,
        )
        child_qg = QuestionGroup.objects.create(
            form=child_form, name="Visit Details", order=1
        )
        cq1 = Questions.objects.create(
            form=child_form,
            question_group=child_qg,
            name="visitor_name",
            type=QuestionTypes.input,
            order=1,
        )
        cq2 = Questions.objects.create(
            form=child_form,
            question_group=child_qg,
            name="facility_status",
            type=QuestionTypes.option,
            order=2,
        )
        QuestionOptions.objects.create(
            question=cq2, value="1", label="Operational", order=1
        )
        QuestionOptions.objects.create(
            question=cq2, value="2", label="Closed", order=2
        )

        cq3 = Questions.objects.create(
            form=child_form,
            question_group=child_qg,
            name="visit_notes",
            type=QuestionTypes.text,
            order=3,
        )

        # Seed parent submission
        parent_fd = FormData.objects.create(
            form=parent_form,
            name="Clinic Alpha",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=parent_fd,
            question=pq1,
            name="Clinic Alpha",
            created_by=self.user,
        )

        # Seed child submission
        child_fd = FormData.objects.create(
            form=child_form,
            parent=parent_fd,
            name="Visit 1",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=child_fd,
            question=cq1,
            name="Inspector Gadget",
            created_by=self.user,
        )
        Answers.objects.create(
            data=child_fd,
            question=cq2,
            options=["1"],
            created_by=self.user,
        )
        Answers.objects.create(
            data=child_fd,
            question=cq3,
            name="Looking great",
            created_by=self.user,
        )

        test_file = "./tmp/test_monitoring_order.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_monitoring_data_sheet(
                writer=writer,
                parent_form=parent_form,
                child_form=child_form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        df = pd.read_excel(test_file, sheet_name="data")
        expected_columns = monitoring_meta_columns + [
            "visitor_name",
            "facility_status",
            "visit_notes",
        ]
        self.assertEqual(list(df.columns), expected_columns)
        self.assertEqual(df["facility_status"].iloc[0], "Operational")

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_generate_data_sheet_repeatable_questions_ordering(self):
        """
        Verify that repeatable question groups output indexed columns in
        proper schema sequence and labels are resolved for repeatable
        option questions.
        """
        form = Forms.objects.create(
            name="Household Survey",
            created_by=self.user,
        )
        qg1 = QuestionGroup.objects.create(
            form=form, name="Household Info", order=1
        )
        q1 = Questions.objects.create(
            form=form,
            question_group=qg1,
            name="head_of_household",
            type=QuestionTypes.input,
            order=1,
        )

        qg2 = QuestionGroup.objects.create(
            form=form, name="Members", order=2, repeatable=True
        )
        q2 = Questions.objects.create(
            form=form,
            question_group=qg2,
            name="member_name",
            type=QuestionTypes.input,
            order=1,
        )
        q3 = Questions.objects.create(
            form=form,
            question_group=qg2,
            name="member_relation",
            type=QuestionTypes.option,
            order=2,
        )
        QuestionOptions.objects.create(
            question=q3, value="1", label="Spouse", order=1
        )
        QuestionOptions.objects.create(
            question=q3, value="2", label="Child", order=2
        )

        qg3 = QuestionGroup.objects.create(
            form=form, name="Survey Notes", order=3
        )
        q4 = Questions.objects.create(
            form=form,
            question_group=qg3,
            name="survey_notes",
            type=QuestionTypes.text,
            order=1,
        )

        fd = FormData.objects.create(
            form=form,
            name="Household 1",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        Answers.objects.create(
            data=fd,
            question=q1,
            name="Alice Smith",
            created_by=self.user,
        )
        # Repeat 1 (index 0)
        Answers.objects.create(
            data=fd,
            question=q2,
            name="Bob Smith",
            index=0,
            created_by=self.user,
        )
        Answers.objects.create(
            data=fd,
            question=q3,
            options=["1"],
            index=0,
            created_by=self.user,
        )
        # Repeat 2 (index 1)
        Answers.objects.create(
            data=fd,
            question=q2,
            name="Charlie Smith",
            index=1,
            created_by=self.user,
        )
        Answers.objects.create(
            data=fd,
            question=q3,
            options=["2"],
            index=1,
            created_by=self.user,
        )
        # Group 3
        Answers.objects.create(
            data=fd,
            question=q4,
            name="Completed smoothly",
            created_by=self.user,
        )

        test_file = "./tmp/test_repeatable_order.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        df = pd.read_excel(test_file, sheet_name="data")
        expected_columns = meta_columns + [
            "head_of_household",
            "member_name_1",
            "member_name_2",
            "member_relation_1",
            "member_relation_2",
            "survey_notes",
        ]
        self.assertEqual(list(df.columns), expected_columns)
        self.assertEqual(df["member_relation_1"].iloc[0], "Spouse")
        self.assertEqual(df["member_relation_2"].iloc[0], "Child")

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_get_answer_label_negative_and_edge_cases(self):
        """
        Negative tests for get_answer_label:
        1. None / NaN values return safely without exception.
        2. Non-existent question ID returns original value.
        3. Non-existent option value returns original value.
        4. Partial match in multi-option handles missing options gracefully.
        5. Numeric / float input converts properly.
        """
        # 1. None and NaN inputs
        self.assertIsNone(get_answer_label(None, 999999))
        self.assertTrue(pd.isna(get_answer_label(float("nan"), 999999)))

        # 2. Non-existent question ID
        self.assertEqual(get_answer_label("1", 999999), "1")

        # Create a real question with options for negative option lookups
        form = Forms.objects.create(
            name="Edge Case Form", created_by=self.user
        )
        qg = QuestionGroup.objects.create(form=form, name="Group", order=1)
        q = Questions.objects.create(
            form=form,
            question_group=qg,
            name="test_option_q",
            type=QuestionTypes.option,
            order=1,
        )
        QuestionOptions.objects.create(
            question=q, value="1", label="Option One", order=1
        )

        # 3. Non-existent option value
        self.assertEqual(get_answer_label("999", q.id), "999")
        self.assertEqual(
            get_answer_label("non_existent_value", q.id), "non_existent_value"
        )

        # 4. Partial match in multi-option string
        self.assertEqual(get_answer_label("1|999", q.id), "Option One")

        # 5. Numeric inputs (integer and float)
        self.assertEqual(get_answer_label(1.0, q.id), "Option One")
        self.assertEqual(get_answer_label(999, q.id), "999")

    def test_resolve_base_question_name_edge_cases(self):
        """
        Edge case tests for _resolve_base_question_name:
        1. Exact match with underscores in question name.
        2. Repeatable index suffix (_1, _10).
        3. Invalid non-numeric suffix returns None.
        4. Non-matching name returns None.
        """
        question_map = {
            "water_source_type": {"id": 1},
            "age": {"id": 2},
        }

        # Exact matches
        self.assertEqual(
            _resolve_base_question_name("water_source_type", question_map),
            "water_source_type",
        )
        self.assertEqual(
            _resolve_base_question_name("age", question_map), "age"
        )

        # Indexed repeatable matches
        self.assertEqual(
            _resolve_base_question_name("water_source_type_1", question_map),
            "water_source_type",
        )
        self.assertEqual(
            _resolve_base_question_name("water_source_type_12", question_map),
            "water_source_type",
        )
        self.assertEqual(
            _resolve_base_question_name("age_3", question_map), "age"
        )

        # Negative / non-matching cases
        self.assertIsNone(
            _resolve_base_question_name(
                "water_source_type_extra", question_map
            )
        )
        self.assertIsNone(
            _resolve_base_question_name("unknown_question", question_map)
        )
        self.assertIsNone(
            _resolve_base_question_name("unknown_question_1", question_map)
        )
        self.assertIsNone(_resolve_base_question_name("", question_map))

    def test_generate_data_sheet_empty_submissions_generates_blank_template(
        self,
    ):
        """
        Negative test: When form has 0 submissions, generate_data_sheet
        falls back to blank_data_template without crashing, preserving
        the definition sheet and column layout.
        """
        form = Forms.objects.create(
            name="Empty Submissions Form",
            created_by=self.user,
        )
        qg = QuestionGroup.objects.create(form=form, name="Group 1", order=1)
        Questions.objects.create(
            form=form,
            question_group=qg,
            name="q_text",
            type=QuestionTypes.input,
            order=1,
        )
        Questions.objects.create(
            form=form,
            question_group=qg,
            name="q_option",
            type=QuestionTypes.option,
            order=2,
        )

        test_file = "./tmp/test_empty_submissions.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        # Should create valid excel file with data and definition sheets
        excel = pd.ExcelFile(test_file)
        self.assertIn("data", excel.sheet_names)
        self.assertIn("questions", excel.sheet_names)

        df = pd.read_excel(test_file, sheet_name="data")
        expected_columns = meta_columns + ["q_text", "q_option"]
        self.assertEqual(list(df.columns), expected_columns)
        self.assertEqual(len(df), 0)

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_generate_data_sheet_with_invalid_option_values_and_null_answers(
        self,
    ):
        """
        Negative test: When answers contain corrupt/invalid option values
        or null/empty strings, generate_data_sheet processes them gracefully
        without throwing exceptions, preserving original values and
        column order.
        """
        form = Forms.objects.create(
            name="Corrupt Answers Form",
            created_by=self.user,
        )
        qg = QuestionGroup.objects.create(form=form, name="Group 1", order=1)
        Questions.objects.create(
            form=form,
            question_group=qg,
            name="name",
            type=QuestionTypes.input,
            order=1,
        )
        q2 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="status",
            type=QuestionTypes.option,
            order=2,
        )
        QuestionOptions.objects.create(
            question=q2, value="1", label="Active", order=1
        )
        q3 = Questions.objects.create(
            form=form,
            question_group=qg,
            name="remarks",
            type=QuestionTypes.text,
            order=3,
        )

        fd = FormData.objects.create(
            form=form,
            name="Corrupt Submitter",
            geo=[6.2, 106.8],
            administration=self.administration,
            created_by=self.user,
        )
        # q1 is empty / None
        # q2 has non-existent option value "999"
        Answers.objects.create(
            data=fd, question=q2, options=["999"], created_by=self.user
        )
        # q3 is empty string
        Answers.objects.create(
            data=fd, question=q3, name="", created_by=self.user
        )

        test_file = "./tmp/test_corrupt_answers.xlsx"
        if os.path.exists(test_file):
            os.remove(test_file)

        with pd.ExcelWriter(test_file, engine="xlsxwriter") as writer:
            generate_data_sheet(
                writer=writer,
                form=form,
                use_label=True,
                download_type=DataDownloadTypes.recent,
                user=self.user,
            )

        df = pd.read_excel(test_file, sheet_name="data")
        expected_columns = meta_columns + ["name", "status", "remarks"]
        self.assertEqual(list(df.columns), expected_columns)
        # Invalid option should be kept as "999" (not crash or blank out)
        self.assertEqual(str(df["status"].iloc[0]), "999")

        if os.path.exists(test_file):
            os.remove(test_file)
