import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms


def minimal_form(form_id, name, question_id):
    """Smallest definition normalize_form_definition() accepts.

    Legacy seeder shape: form/question_groups/questions. Types are strings
    here because the normalizer maps them to QuestionTypes constants.
    """
    return {
        "id": form_id,
        "form": name,
        "version": 1,
        "type": 1,
        "question_groups": [
            {
                "id": form_id * 100,
                "order": 1,
                "name": "group_01",
                "label": "Group 01",
                "questions": [
                    {
                        "id": question_id,
                        "order": 1,
                        "name": "full_name",
                        "label": "Full Name",
                        "short_label": "Name",
                        "meta": True,
                        "type": "text",
                        "required": True,
                    }
                ],
            }
        ],
    }


@override_settings(USE_TZ=False, TEST_ENV=True)
class FormSeederFileSelectionTestCase(TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp(prefix="form_seeder_select_")
        self.addCleanup(shutil.rmtree, self.source, ignore_errors=True)
        self.write("example-alpha.json", minimal_form(801, "Alpha", 80101))
        self.write("client-beta.json", minimal_form(802, "Beta", 80201))

    def write(self, filename, payload):
        path = os.path.join(self.source, filename)
        with open(path, "w") as handle:
            json.dump(payload, handle)

    def seed(self, *args):
        out = StringIO()
        call_command(
            "form_seeder",
            *args,
            source=self.source,
            stdout=out,
            stderr=StringIO(),
        )
        return out.getvalue()

    def test_plain_run_loads_every_json(self):
        """No flag: every *.json in the folder is seeded, whatever it
        is named. This is the point of the change — real deployments
        drop their own definitions here."""
        self.seed()
        self.assertTrue(Forms.objects.filter(pk=801).exists())
        self.assertTrue(Forms.objects.filter(pk=802).exists())

    def test_test_flag_narrows_to_examples(self):
        """--test still selects only the bundled example fixtures, so
        the 110 existing call sites keep their current meaning."""
        self.seed("--test", 1)
        self.assertTrue(Forms.objects.filter(pk=801).exists())
        self.assertFalse(Forms.objects.filter(pk=802).exists())
