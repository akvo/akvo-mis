import os
from pathlib import Path
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_profile.management.commands import administration_seeder

config_path = "source/config/config.min.js"


@override_settings(USE_TZ=False)
class ConfigJS(TestCase):
    def test_config_generation(self):
        administration_seeder.seed_administration_test()
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
        # levels left the bake too once they became tenant-owned; what
        # stays is per-deployment, not per-tenant.
        for expected in ("var appConfig", "var roleFeatures"):
            self.assertIn(expected, content)

    def test_config_has_no_levels_block(self):
        administration_seeder.seed_administration_test()
        if Path(config_path).exists():
            os.remove(config_path)
        self.client.get("/api/v1/config.js", follow=True)
        with open(config_path) as f:
            content = f.read()
        os.remove(config_path)
        self.assertNotIn("var levels", content)

    @override_settings(TURNSTILE_SITE_KEY="0xSITEKEY")
    def test_config_carries_the_turnstile_site_key(self):
        """The frontend cannot read a Django setting.

        appConfig is how every other deployment-wide value reaches it,
        and the site key is public by design -- it is meant to be in
        the page.
        """
        if Path(config_path).exists():
            os.remove(config_path)
        call_command("generate_config")
        with open(config_path) as f:
            content = f.read()
        os.remove(config_path)
        self.assertIn("0xSITEKEY", content)
