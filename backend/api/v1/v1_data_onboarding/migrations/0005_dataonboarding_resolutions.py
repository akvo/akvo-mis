from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v1_data_onboarding', '0004_dataonboarding_revised'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataonboarding',
            name='resolutions',
            field=models.JSONField(default=dict),
        ),
    ]
