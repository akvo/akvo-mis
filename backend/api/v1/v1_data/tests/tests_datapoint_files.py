"""APP-517: every listed datapoint has a current file.

Storage is redirected to a temporary folder for every test: the reconcile
deletes files, and the real folder holds a developer's data locally and other
parallel workers' files in CI.
"""
import os
from importlib import import_module
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings

from api.v1.v1_data.tasks import reconcile_datapoint_files
from api.v1.v1_data.models import Answers, FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Forms, QuestionGroup, Questions
from api.v1.v1_profile.models import Administration
from api.v1.v1_profile.tests.mixins import ProfileTestHelperMixin


@override_settings(TEST_ENV=True)
class DatapointFilesTestCase(TestCase, ProfileTestHelperMixin):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("default_roles_seeder", "--test", 1)
        self.administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        self.user = self.create_user(
            email="admin@test.org",
            role_level=self.IS_SUPER_ADMIN,
            administration=self.administration,
        )
        self.form = self.make_form("Registration")
        self.monitoring = self.make_form("Monitoring", parent=self.form)

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch("utils.storage.STORAGE_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = Path(tmp.name) / "datapoints"

    def make_form(self, name, parent=None):
        form = Forms.objects.create(name=name, version=1, parent=parent)
        group = QuestionGroup.objects.create(form=form, name="G", order=1)
        form.text_question = Questions.objects.create(
            form=form, question_group=group, name="farmer",
            label="Farmer", order=1, type=QuestionTypes.input,
        )
        return form

    def make_datapoint(self, name, form=None, **fields):
        form = form or self.form
        data = FormData.objects.create(
            name=name, form=form, administration=self.administration,
            created_by=self.user, uuid=f"uuid-{name}", **fields,
        )
        Answers.objects.create(
            data=data, question=form.text_question, name=name,
            created_by=self.user,
        )
        return data

    def file_of(self, data):
        return self.folder / f"{data.uuid}.json"

    def stamp_of(self, data):
        return FormData._base_manager.get(pk=data.pk).file_generated_at

    # DatapointFile.write_file

    def test_writes_the_file_and_stamps_the_row(self):
        data = self.make_datapoint("a")
        self.assertTrue(data.write_file())
        self.assertTrue(self.file_of(data).exists())
        self.assertIsNotNone(self.stamp_of(data))

    def test_a_failed_write_leaves_the_row_owed_and_does_not_raise(self):
        data = self.make_datapoint("a")
        self.addCleanup(
            lambda: os.path.exists(f"{data.uuid}.json")
            and os.remove(f"{data.uuid}.json")
        )
        with mock.patch(
            "utils.storage.upload", side_effect=OSError("disk full")
        ):
            self.assertFalse(data.write_file())
        self.assertIsNone(self.stamp_of(data))

    def test_a_monitoring_row_gets_no_file(self):
        data = self.make_datapoint("m", form=self.monitoring)
        self.assertFalse(data.write_file())
        self.assertFalse(self.file_of(data).exists())
        self.assertIsNone(self.stamp_of(data))

    def test_downloadable_agrees_with_needs_file(self):
        """`FILE_EXEMPT` (the listing) and `needs_file()` (the writer) say
        the same thing twice; this keeps them from drifting apart."""
        written = self.make_datapoint("written")
        written.write_file()
        owed = self.make_datapoint("owed")
        visit = self.make_datapoint("visit", form=self.monitoring)
        self.assertTrue(owed.needs_file())
        self.assertFalse(visit.needs_file())
        self.assertEqual(
            sorted(FormData.objects.downloadable().values_list(
                "name", flat=True
            )),
            ["visit", "written"],
        )

    # FormData.finalize

    @mock.patch("api.v1.v1_data.models.async_task")
    def test_finalize_writes_on_commit_and_still_queues_the_task(self, task):
        data = self.make_datapoint("a")
        with self.captureOnCommitCallbacks(execute=True):
            data.finalize()
            # Nothing before commit: a rolled-back submission has no file.
            self.assertFalse(self.file_of(data).exists())
        self.assertTrue(self.file_of(data).exists())
        self.assertIsNotNone(self.stamp_of(data))
        task.assert_called_once_with(
            "api.v1.v1_data.tasks.seed_approved_data", data
        )

    @mock.patch("api.v1.v1_data.models.async_task")
    def test_a_rolled_back_submission_writes_nothing(self, task):
        data = self.make_datapoint("a")
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    data.finalize()
                    raise RuntimeError("submission failed")
            except RuntimeError:
                pass
        self.assertEqual(callbacks, [])
        self.assertFalse(self.file_of(data).exists())

    # reconcile: rewriting

    def test_reconcile_rewrites_only_what_is_owed(self):
        current = self.make_datapoint("current")
        current.write_file()
        self.make_datapoint("never")
        stale = self.make_datapoint("stale")
        stale.write_file()
        # Edited after its file was written.
        FormData.objects.filter(pk=stale.pk).update(
            updated=self.stamp_of(stale) + timedelta(microseconds=1)
        )
        vanished = self.make_datapoint("vanished")
        vanished.write_file()
        self.file_of(vanished).unlink()
        self.make_datapoint("draft", is_draft=True)
        self.make_datapoint("pending", is_pending=True)

        result = reconcile_datapoint_files()

        self.assertEqual(
            sorted(result["rewritten"]),
            ["uuid-never", "uuid-stale", "uuid-vanished"],
        )
        self.assertTrue(self.file_of(vanished).exists())
        self.assertGreaterEqual(
            self.stamp_of(stale),
            FormData.objects.get(pk=stale.pk).updated,
        )

    def test_reconcile_all_rewrites_every_published_row(self):
        current = self.make_datapoint("current")
        current.write_file()
        result = reconcile_datapoint_files(rewrite_all=True)
        self.assertEqual(result["rewritten"], ["uuid-current"])

    def test_dry_run_changes_nothing(self):
        owed = self.make_datapoint("owed")
        for name in ("a", "b", "c"):
            self.make_datapoint(name).write_file()
        (self.folder / "orphan.json").write_text("{}")

        result = reconcile_datapoint_files(dry_run=True)

        self.assertEqual(result["rewritten"], ["uuid-owed"])
        self.assertEqual(result["deleted"], ["orphan"])
        self.assertFalse(self.file_of(owed).exists())
        self.assertTrue((self.folder / "orphan.json").exists())

    # reconcile: cleanup

    def test_deletes_orphans_and_unstamps_a_soft_deleted_row(self):
        for name in ("a", "b", "c"):
            self.make_datapoint(name).write_file()
        deleted = self.make_datapoint("deleted")
        deleted.write_file()
        deleted.delete()
        (self.folder / "gone.json").write_text("{}")
        # A pending edit shares its uuid with the published original.
        original = FormData.objects.get(uuid="uuid-a")
        edit = self.make_datapoint("edit", is_pending=True)
        FormData.objects.filter(pk=edit.pk).update(uuid=original.uuid)

        result = reconcile_datapoint_files()

        self.assertEqual(sorted(result["deleted"]), ["gone", "uuid-deleted"])
        self.assertFalse(self.file_of(deleted).exists())
        self.assertTrue(self.file_of(original).exists())
        # Restored, it must read as owed, not as current with no file.
        self.assertIsNone(self.stamp_of(deleted))
        FormData.objects_deleted.filter(pk=deleted.pk).restore()
        self.assertIn(
            "uuid-deleted", reconcile_datapoint_files()["rewritten"]
        )

    def test_refuses_to_delete_most_of_the_folder_unless_forced(self):
        self.make_datapoint("a").write_file()
        for name in ("x", "y"):
            (self.folder / f"{name}.json").write_text("{}")

        # A dry run is read before deciding on --force: it must not promise
        # deletions the real run would refuse.
        dry = reconcile_datapoint_files(dry_run=True)
        self.assertEqual(dry["deleted"], [])
        self.assertEqual(sorted(dry["refused"]), ["x", "y"])

        refused = reconcile_datapoint_files()
        self.assertEqual(refused["deleted"], [])
        self.assertEqual(sorted(refused["refused"]), ["x", "y"])
        self.assertTrue((self.folder / "x.json").exists())

        forced = reconcile_datapoint_files(force=True)
        self.assertEqual(sorted(forced["deleted"]), ["x", "y"])
        self.assertFalse((self.folder / "x.json").exists())

    def test_refuses_when_the_database_has_no_published_rows(self):
        # A run against the wrong database: every file looks orphaned.
        self.folder.mkdir(parents=True)
        (self.folder / "x.json").write_text("{}")
        for name in ("a", "b", "c"):
            (self.folder / f"uuid-{name}.json").write_text("{}")
        result = reconcile_datapoint_files()
        self.assertEqual(result["deleted"], [])
        self.assertTrue((self.folder / "x.json").exists())

    def test_a_file_written_after_the_listing_is_never_deleted(self):
        """The folder is listed before the database is queried. Swap the
        order and a datapoint committing in between has its fresh file
        taken for an orphan."""
        for name in ("a", "b", "c"):
            self.make_datapoint(name).write_file()
        late = {}
        glob = Path.glob

        def commit_during_listing(folder, pattern):
            listed = list(glob(folder, pattern))
            late["data"] = self.make_datapoint("late")
            late["data"].write_file()
            return iter(listed)

        with mock.patch.object(Path, "glob", commit_during_listing):
            result = reconcile_datapoint_files()

        self.assertNotIn("uuid-late", result["deleted"])
        self.assertTrue(self.file_of(late["data"]).exists())


class ReconcileScheduleTestCase(TestCase):
    def test_the_migration_schedules_the_reconcile_once(self):
        migration = import_module(
            "api.v1.v1_data.migrations.0006_formdata_file_generated_at"
        )
        Schedule = apps.get_model("django_q", "Schedule")
        rows = Schedule.objects.filter(name=migration.NAME)
        self.assertEqual(
            list(rows.values_list("func", "schedule_type")),
            [("api.v1.v1_data.tasks.reconcile_datapoint_files", "H")],
        )
        # A replay must not schedule it twice.
        migration.schedule(apps, None)
        self.assertEqual(rows.count(), 1)
        # And the path it names must still import.
        module, name = migration.FUNC.rsplit(".", 1)
        self.assertTrue(callable(getattr(import_module(module), name)))
