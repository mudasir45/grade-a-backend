# Generated by Django 5.1.6 on 2025-03-13 16:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_city_remove_driverprofile_commission_rate_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone_number",
            field=models.CharField(blank=True, max_length=15, unique=True),
        ),
    ]
