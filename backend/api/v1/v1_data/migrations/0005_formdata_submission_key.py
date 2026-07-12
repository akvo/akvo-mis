from django.db import migrations, models


class Migration(migrations.Migration):
    """Per-submission idempotency key on FormData.

    `data` grows without bound, so the column and its unique index are added
    separately. AddField on a nullable column with no default is metadata-only
    in Postgres 12, but the unique index implied by `unique=True` would scan
    and lock the whole table under ACCESS EXCLUSIVE. Building it CONCURRENTLY
    keeps reads and writes running.

    IF NOT EXISTS / DROP ... IF EXISTS matter: CREATE INDEX CONCURRENTLY can
    fail part-way and leave an INVALID index behind, and the retry must not
    trip over it.
    """

    atomic = False  # CREATE INDEX CONCURRENTLY can't run in a txn

    dependencies = [
        ("v1_data", "0004_formdata_published_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="formdata",
            name="submission_key",
            field=models.CharField(max_length=64, null=True, default=None),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                        "data_submission_key_uniq ON data (submission_key);"
                    ),
                    reverse_sql=(
                        "DROP INDEX CONCURRENTLY IF EXISTS "
                        "data_submission_key_uniq;"
                    ),
                ),
            ],
            # Django's model state still believes the field is unique.
            state_operations=[
                migrations.AlterField(
                    model_name="formdata",
                    name="submission_key",
                    field=models.CharField(
                        max_length=64, null=True, unique=True, default=None
                    ),
                ),
            ],
        ),
    ]
