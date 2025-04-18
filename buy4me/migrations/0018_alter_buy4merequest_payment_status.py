# Generated by Django 5.0.2 on 2025-04-12 06:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buy4me", "0017_buy4merequest_service_fee_percentage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="buy4merequest",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PAID", "Paid"),
                    ("REFUNDED", "Refunded"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
