"""Move the embed entitlement out of the environment and into the row.

`EMBED_TENANTS` was a comma-separated environment variable parsed at
startup, so selling the feature to a customer meant a deploy. It is
deleted in the same commit as this migration.

The value is read from os.environ rather than django.conf.settings
precisely because the setting is going away: a migration replayed on a
fresh database months from now must not depend on a setting that no
longer exists.
"""
import os

from django.db import migrations

EMBEDDED_DASHBOARD = "embedded_dashboard"


def backfill(apps, schema_editor):
    Tenant = apps.get_model("v1_users", "Tenant")
    entitled = {
        part.strip().lower()
        for part in os.environ.get("EMBED_TENANTS", "").split(",")
        if part.strip()
    }
    if not entitled:
        return
    for tenant in Tenant.objects.filter(subdomain__in=entitled):
        features = dict(tenant.features or {})
        features[EMBEDDED_DASHBOARD] = True
        tenant.features = features
        tenant.save(update_fields=["features"])


def unbackfill(apps, schema_editor):
    """Clear the flag everywhere; EMBED_TENANTS becomes authoritative
    again on the way back down."""
    Tenant = apps.get_model("v1_users", "Tenant")
    for tenant in Tenant.objects.exclude(features={}):
        features = dict(tenant.features or {})
        features.pop(EMBEDDED_DASHBOARD, None)
        tenant.features = features
        tenant.save(update_fields=["features"])


class Migration(migrations.Migration):

    dependencies = [
        ("v1_users", "0008_tenant_lifecycle"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
