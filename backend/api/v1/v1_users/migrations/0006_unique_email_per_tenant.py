# Generated for MT-013 cross-tenant email sharing

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v1_users', '0005_systemuser_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemuser',
            name='email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AddConstraint(
            model_name='systemuser',
            constraint=models.UniqueConstraint(
                fields=['email', 'tenant'],
                name='unique_email_per_tenant'
            ),
        ),
    ]
