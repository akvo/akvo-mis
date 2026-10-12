from django.test import TestCase, override_settings

from api.v1.v1_profile.constants import FeatureFlags
from api.v1.v1_users.models import Tenant
from utils.tenant_host import tenant_may_embed


@override_settings(EMBED_HOST="https://embed.app.com")
class TenantFeaturesTestCase(TestCase):
    """Entitlement is per workspace and lives in the database.

    EMBED_HOST stays the deployment's capability -- without an origin of
    its own there is nowhere safe to run a third-party snippet, whatever
    was sold. What moved is the commercial half.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(subdomain="acme")

    def test_off_by_default(self):
        self.assertFalse(tenant_may_embed(self.tenant))

    def test_on_when_the_flag_is_set(self):
        self.tenant.features = {FeatureFlags.embedded_dashboard: True}
        self.tenant.save(update_fields=["features"])
        self.assertTrue(tenant_may_embed(self.tenant))

    def test_a_tenant_less_caller_is_never_entitled(self):
        self.assertFalse(tenant_may_embed(None))

    @override_settings(EMBED_HOST="")
    def test_no_embed_host_overrides_the_flag(self):
        self.tenant.features = {FeatureFlags.embedded_dashboard: True}
        self.tenant.save(update_fields=["features"])
        self.assertFalse(tenant_may_embed(self.tenant))

    def test_every_flag_has_a_label(self):
        # generate_config and the console's toggle list both walk
        # FieldStr, so a key without one renders as a blank switch.
        self.assertIn(
            FeatureFlags.embedded_dashboard, FeatureFlags.FieldStr
        )
