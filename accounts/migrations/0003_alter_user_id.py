# Generated by Django 5.1.6 on 2025-02-18 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_country"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="id",
            field=models.CharField(
                editable=False, max_length=12, primary_key=True, serialize=False
            ),
        ),
    ]
