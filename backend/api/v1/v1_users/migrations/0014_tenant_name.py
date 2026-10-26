from django.db import migrations, models


def backfill_tenant_name(apps, schema_editor):
    Tenant = apps.get_model("v1_users", "Tenant")
    for tenant in Tenant.objects.all():
        if not tenant.name:
            tenant.name = tenant.subdomain
            tenant.save(update_fields=["name"])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('v1_users', '0013_tenant_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(backfill_tenant_name, reverse_backfill),
    ]
