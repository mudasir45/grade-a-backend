# Generated by Django 5.0.2 on 2025-03-29 16:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipments", "0030_shipmentrequest_awb"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="admin_reply",
            field=models.TextField(
                blank=True, help_text="Admin reply to the ticket", null=True
            ),
        ),
    ]
