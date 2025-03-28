# Generated by Django 5.1.6 on 2025-03-03 07:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipping_rates", "0006_servicetype_price"),
    ]

    operations = [
        migrations.AlterField(
            model_name="additionalcharge",
            name="zones",
            field=models.ManyToManyField(
                blank=True,
                related_name="additional_charges",
                to="shipping_rates.shippingzone",
            ),
        ),
    ]
