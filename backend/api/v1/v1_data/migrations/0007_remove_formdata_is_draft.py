from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("v1_data", "0006_purge_server_drafts"),
        ("v1_visualization", "0006_drop_view_data_options"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS idx_data_latest_monitoring;",
            reverse_sql=(
                "CREATE INDEX IF NOT EXISTS idx_data_latest_monitoring "
                "ON data (form_id, parent_id, created DESC) "
                "WHERE is_pending = FALSE AND is_draft = FALSE;"
            ),
        ),
        migrations.RemoveField(
            model_name="formdata",
            name="is_draft",
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS idx_data_latest_monitoring "
                "ON data (form_id, parent_id, created DESC) "
                "WHERE is_pending = FALSE;"
            ),
            reverse_sql="DROP INDEX IF EXISTS idx_data_latest_monitoring;",
        ),
    ]
