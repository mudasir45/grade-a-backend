# Generated by Django 5.1.6 on 2025-02-06 12:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipments", "0002_alter_shipmentrequest_id_alter_shipmenttracking_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipmentrequest",
            name="id",
            field=models.CharField(
                editable=False, max_length=12, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="shipmenttracking",
            name="id",
            field=models.CharField(
                editable=False, max_length=12, primary_key=True, serialize=False
            ),
        ),
    ]
