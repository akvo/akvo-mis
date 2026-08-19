from django.db import migrations

# Every table that gained a tenant FK, plus SystemUser (whose FK landed
# in the registration iteration). _base_manager everywhere: several of
# these models have SoftDeletes managers whose default queryset hides
# soft-deleted rows, and the backfill must stamp those too.
TARGETS = [
    ("v1_users", "SystemUser"),
    ("v1_users", "Organisation"),
    ("v1_profile", "Levels"),
    ("v1_profile", "Administration"),
    ("v1_profile", "Entity"),
    ("v1_profile", "AdministrationAttribute"),
    ("v1_forms", "Forms"),
]


def backfill_default_tenant(apps, schema_editor):
    Tenant = apps.get_model("v1_users", "Tenant")
    tenant, _ = Tenant.objects.get_or_create(subdomain="default")
    for app_label, model_name in TARGETS:
        model = apps.get_model(app_label, model_name)
        model._base_manager.filter(tenant__isnull=True).update(tenant=tenant)


def remove_default_tenant(apps, schema_editor):
    Tenant = apps.get_model("v1_users", "Tenant")
    tenant = Tenant.objects.filter(subdomain="default").first()
    if not tenant:
        return
    for app_label, model_name in TARGETS:
        model = apps.get_model(app_label, model_name)
        model._base_manager.filter(tenant=tenant).update(tenant=None)
    tenant.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("v1_users", "0003_organisation_tenant_alter_organisation_name_and_more"),
        (
            "v1_profile",
            "0007_administration_tenant_administrationattribute_tenant_and_more",
        ),
        ("v1_forms", "0009_forms_tenant"),
    ]

    operations = [
        migrations.RunPython(backfill_default_tenant, remove_default_tenant),
    ]
