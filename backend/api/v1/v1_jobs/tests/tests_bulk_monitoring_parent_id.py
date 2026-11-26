import os
import tempfile

import pandas as pd
from django.core.management import call_command
from django.test import TestCase, override_settings

from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_jobs.constants import JobStatus, JobTypes
from api.v1.v1_jobs.functions import ValidationText
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_jobs.seed_data import (
    collect_answers,
    get_administration,
    get_geo_value,
    seed_excel_data,
)
from api.v1.v1_jobs.validate_upload import validate, validate_administration
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin
from utils.export_form import blank_data_template


@override_settings(USE_TZ=False, TEST_ENV=True)
class BulkMonitoringParentIdTestCase(TestCase, ProfileTestHelperMixin):
    """JOB-580: bulk monitoring upload must link rows to their registration
    parent via the parent_id column, and the blank template for a child form
    must expose that column."""

    def setUp(self):
        call_command("form_seeder", "--test")
        rows = [{
            "code_0": "ID", "National_0": "Indonesia",
            "code_1": "ID-JK", "Province_1": "Jakarta",
            "code_2": "ID-JK-JKE", "District_2": "East Jakarta",
            "code_3": "ID-JK-JKE-KJ", "Subdistrict_3": "Kramat Jati",
            "code_4": "ID-JK-JKE-KJ-CW", "Village_4": "Cawang",
        }]
        administration_seeder.seed_administration_test(rows=rows)

        self.user = SystemUser.objects.create(
            email="admin@akvo.org",
            first_name="Admin",
            last_name="Akvo",
            is_superuser=True,
        )
        self.form = Forms.objects.get(pk=1)
        self.child_form = self.form.children.first()
        self.administration = Administration.objects.get(name="Cawang")
        self.text_question = Questions.objects.filter(
            form=self.child_form, type=QuestionTypes.text
        ).first()

        # A registration datapoint on the parent form to attach monitoring to.
        self.parent_dp = FormData.objects.create(
            name="Registration One",
            form=self.form,
            administration=self.administration,
            geo=["-6.2", "106.8"],
            created_by=self.user,
        )

    def _write_sheet(self, rows):
        path = os.path.join(tempfile.mkdtemp(), "monitoring.xlsx")
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            pd.DataFrame(rows).to_excel(
                writer, sheet_name="data", index=False
            )
        return path

    def _row(self, parent_id, answer="08123456789"):
        # administration/geolocation columns must exist: collect_answers reads
        # them by key. They are overridden from the parent for monitoring rows.
        return {
            self.text_question.name: answer,
            "administration": None,
            "geolocation": None,
            "parent_id": parent_id,
        }

    # ---- validate() -----------------------------------------------------

    def test_validate_missing_parent_id_column_errors(self):
        path = self._write_sheet([{
            self.text_question.name: "08123456789",
            "administration": None,
            "geolocation": None,
        }])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            errors[0]["error_message"],
            ValidationText.parent_id_required.value,
        )

    def test_validate_blank_parent_id_errors(self):
        path = self._write_sheet([self._row(None)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            errors[0]["error_message"],
            ValidationText.parent_id_required.value,
        )

    def test_validate_nonexistent_parent_id_errors(self):
        path = self._write_sheet([self._row(999999)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("999999", errors[0]["error_message"])

    def test_validate_wrong_form_parent_id_errors(self):
        # A datapoint that is NOT a registration of this form's parent.
        other = Forms.objects.exclude(pk=self.form.pk).first()
        stray = FormData.objects.create(
            name="Stray",
            form=other,
            administration=self.administration,
            created_by=self.user,
        )
        path = self._write_sheet([self._row(stray.id)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 1)

    def test_validate_valid_parent_id_ok(self):
        path = self._write_sheet([self._row(self.parent_dp.id)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 0)

    def test_validate_parent_outside_uploader_subtree_errors(self):
        # JOB-580 review: a parent_id whose datapoint is outside the uploader's
        # administration subtree must be rejected at validation. save_data
        # inherits the parent's administration and drops rows outside the
        # subtree, so without this check the row passes validation then
        # vanishes silently. Uploader scoped at Cawang (leaf); parent sits at
        # its ancestor East Jakarta, which is not in Cawang's descendants.
        ancestor = Administration.objects.get(name="East Jakarta")
        outside_parent = FormData.objects.create(
            name="Outside subtree",
            form=self.form,
            administration=ancestor,
            created_by=self.user,
        )
        path = self._write_sheet([self._row(outside_parent.id)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn(str(outside_parent.id), errors[0]["error_message"])

    def test_validate_registration_form_unaffected(self):
        # Parent (registration) form has no parent → parent_id not required.
        path = self._write_sheet([{
            "administration": "Indonesia",
            "geolocation": None,
        }])
        errors = validate(
            form=self.form.id,
            administration=self.administration.id,
            file=path,
        )
        required = ValidationText.parent_id_required.value
        parent_msgs = [
            e for e in errors if e.get("error_message") == required
        ]
        self.assertEqual(parent_msgs, [])

    def _add_geo_question(self, form, name):
        return Questions.objects.create(
            form=form,
            question_group=QuestionGroup.objects.filter(form=form).first(),
            name=name,
            type=QuestionTypes.geo,
            order=97,
        )

    def test_validate_registration_requires_geolocation(self):
        # JOB-580: a registration form with a geo question must reject a blank
        # geolocation — the datapoint geo cannot be edited in the platform
        # after insert.
        self._add_geo_question(self.form, "gps")
        path = self._write_sheet([{
            "administration": "Indonesia|Jakarta",
            "geolocation": None,
        }])
        errors = validate(
            form=self.form.id,
            administration=self.administration.id,
            file=path,
        )
        required = ValidationText.geo_required.value
        self.assertTrue(
            any(e.get("error_message") == required for e in errors)
        )

    def test_validate_registration_valid_geolocation_ok(self):
        self._add_geo_question(self.form, "gps")
        path = self._write_sheet([{
            "administration": "Indonesia|Jakarta",
            "geolocation": "7.28, 168.82",
        }])
        errors = validate(
            form=self.form.id,
            administration=self.administration.id,
            file=path,
        )
        required = ValidationText.geo_required.value
        self.assertFalse(
            any(e.get("error_message") == required for e in errors)
        )

    def test_validate_registration_edit_row_blank_geo_ok(self):
        # JOB-580 review: geo is required only on NEW rows. An edit row
        # (data_id set) with a blank geolocation must pass — the datapoint may
        # never have had a geo, and rejecting it would block "Update Existing".
        self._add_geo_question(self.form, "gps")
        existing = FormData.objects.create(
            name="Existing",
            form=self.form,
            administration=self.administration,
            created_by=self.user,
        )
        path = self._write_sheet([{
            "id": existing.id,
            "administration": "Indonesia|Jakarta",
            "geolocation": None,
        }])
        errors = validate(
            form=self.form.id,
            administration=self.administration.id,
            file=path,
        )
        required = ValidationText.geo_required.value
        self.assertFalse(
            any(e.get("error_message") == required for e in errors)
        )

    def test_validate_monitoring_geolocation_not_required(self):
        # Child (monitoring) forms inherit geo from their parent, so a blank
        # geolocation must NOT trigger geo_required even if the form has a geo
        # question.
        self._add_geo_question(self.child_form, "gps")
        path = self._write_sheet([self._row(self.parent_dp.id)])
        errors = validate(
            form=self.child_form.id,
            administration=self.administration.id,
            file=path,
        )
        required = ValidationText.geo_required.value
        self.assertFalse(
            any(e.get("error_message") == required for e in errors)
        )

    # ---- seed_excel_data() ---------------------------------------------

    def _seed(self, path):
        job = Jobs.objects.create(
            type=JobTypes.seed_data,
            status=JobStatus.done,
            user=self.user,
            info={
                "file": path,
                "form": self.child_form.id,
                "administration": self.administration.id,
                "is_update": False,
            },
        )
        return seed_excel_data(job=job, test=True)

    def test_get_administration_unresolvable_level_returns_none(self):
        # Regression (JOB-580): a name path whose middle level does not exist
        # must reject the whole path (return None), not fall back to the
        # deepest resolved ancestor — misfiling a datapoint under an ancestor
        # is worse than rejecting the row. It must also never raise IndexError.
        self.assertIsNone(
            get_administration("Indonesia|DoesNotExist|AlsoNope")
        )
        # A fully-resolvable path still returns its deepest node.
        self.assertEqual(
            get_administration("Indonesia|Jakarta").name, "Jakarta"
        )

    def test_validate_administration_unresolvable_level_no_crash(self):
        # Regression (JOB-580): validate_administration resolved the cascade
        # answer by name without tenant scope and did `administration.id` with
        # no None guard, so an unresolvable level raised AttributeError and
        # crashed the whole bulk validation. It must return a row error, not
        # raise.
        adm = {
            "id": self.administration.id,
            "name": self.administration.name,
            "tenant_id": self.administration.tenant_id,
        }
        err = validate_administration("Indonesia|DoesNotExist|AlsoNope", adm)
        self.assertIsInstance(err, dict)
        self.assertIn("error_message", err)

    def test_get_geo_value_blank_normalises_to_none(self):
        # Regression (JOB-580): an empty geolocation arrived as NaN (float)
        # and Postgres rejected 'NaN'::json, aborting the whole bulk seed
        # after the first blank-geo row (only the first row imported, no
        # email). Blank must become None; a real pair must still parse.
        self.assertIsNone(get_geo_value(float("nan")))
        self.assertIsNone(get_geo_value(None))
        self.assertIsNone(get_geo_value(""))
        self.assertEqual(get_geo_value("7.28, 168.82"), [7.28, 168.82])

    def test_date_meta_question_populates_name(self):
        # Regression (JOB-580): collect_answers skipped meta date questions,
        # leaving monitoring datapoint names blank.
        group = QuestionGroup.objects.filter(form=self.child_form).first()
        q = Questions.objects.create(
            form=self.child_form,
            question_group=group,
            name="inspection_date",
            type=QuestionTypes.date,
            meta=True,
            order=99,
        )
        dp = {"administration": None, "geolocation": None, q.id: "2026-08-01"}
        result = collect_answers(self.user, dp, {q.id: q}, None)
        self.assertEqual(result["name"], "2026-08-01")

    def test_seed_empty_name_falls_back_to_parent(self):
        # A row with only a non-meta answer persists but yields an empty name,
        # which must fall back to the parent's name (JOB-580).
        nonmeta = Questions.objects.filter(
            form=self.child_form, meta=False
        ).first()
        path = self._write_sheet([{
            nonmeta.name: 5,
            "administration": None,
            "geolocation": None,
            "parent_id": self.parent_dp.id,
        }])
        records = self._seed(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].name, self.parent_dp.name)

    def test_seed_links_parent_and_inherits(self):
        path = self._write_sheet([self._row(self.parent_dp.id)])
        records = self._seed(path)
        self.assertEqual(len(records), 1)
        child = records[0]
        self.assertEqual(child.parent_id, self.parent_dp.id)
        self.assertEqual(str(child.uuid), str(self.parent_dp.uuid))
        self.assertEqual(
            child.administration_id, self.parent_dp.administration_id
        )
        self.assertEqual(child.geo, self.parent_dp.geo)

    # ---- blank_data_template() -----------------------------------------

    def _template_columns(self, form):
        path = os.path.join(tempfile.mkdtemp(), "template.xlsx")
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            blank_data_template(form=form, writer=writer)
        data = pd.read_excel(path, sheet_name="data")
        questions = pd.read_excel(path, sheet_name="questions")
        return list(data.columns), questions

    def test_blank_template_child_form_has_parent_id(self):
        columns, questions = self._template_columns(self.child_form)
        self.assertIn("parent_id", columns)
        self.assertIn("parent_id", list(questions["name"]))

    def test_blank_template_registration_has_no_parent_id(self):
        columns, _ = self._template_columns(self.form)
        self.assertNotIn("parent_id", columns)
