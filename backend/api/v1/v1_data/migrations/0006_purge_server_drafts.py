from django.db import migrations


def purge_drafts(apps, schema_editor):
    FormData = apps.get_model("v1_data", "FormData")
    FormData.objects.filter(is_draft=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("v1_data", "0005_formdata_submission_key"),
    ]

    operations = [
        migrations.RunPython(purge_drafts, migrations.RunPython.noop),
    ]
