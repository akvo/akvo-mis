import os
from pathlib import Path
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.management.commands import administration_seeder

config_path = "source/config/config.min.js"


@override_settings(USE_TZ=False)
class ConfigJS(TestCase):
    def test_config_generation(self):
        administration_seeder.seed_administration_prod()
        if Path(config_path).exists():
            os.remove(config_path)
        self.assertFalse(Path(config_path).exists())
        self.client.get("/api/v1/config.js", follow=True)
        self.assertTrue(Path(config_path).exists())
        os.remove(config_path)

    def test_config_has_no_topojson(self):
        administration_seeder.seed_administration_test()
        if Path(config_path).exists():
            os.remove(config_path)
        self.client.get("/api/v1/config.js", follow=True)
        with open(config_path) as f:
            content = f.read()
        os.remove(config_path)
        self.assertNotIn("var topojson", content)
        for expected in ("var levels", "var appConfig", "var roleFeatures"):
            self.assertIn(expected, content)
