# Generated by Django 5.0.2 on 2025-04-11 05:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0032_remove_usercountry_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="logo",
            field=models.ImageField(blank=True, null=True, upload_to="store_logos/"),
        ),
    ]
