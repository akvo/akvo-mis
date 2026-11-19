from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v1_data_onboarding', '0002_schedule_file_purge'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataonboarding',
            name='blocked',
            field=models.JSONField(default=None, null=True),
        ),
    ]
