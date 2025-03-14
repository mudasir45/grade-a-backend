# Generated by Django 5.1.6 on 2025-02-18 12:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_id"),
        ("shipping_rates", "0006_servicetype_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="default_shipping_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_shipping_method",
                to="shipping_rates.servicetype",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="preferred_currency",
            field=models.CharField(blank=True, default="USD", max_length=10),
        ),
    ]
