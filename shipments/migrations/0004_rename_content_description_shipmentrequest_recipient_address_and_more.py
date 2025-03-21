# Generated by Django 5.1.6 on 2025-02-17 06:13

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipments", "0003_alter_shipmentrequest_id_alter_shipmenttracking_id"),
    ]

    operations = [
        migrations.RenameField(
            model_name="shipmentrequest",
            old_name="content_description",
            new_name="recipient_address",
        ),
        migrations.RenameField(
            model_name="shipmentrequest",
            old_name="delivery_address",
            new_name="sender_address",
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="declared_value",
            field=models.DecimalField(
                decimal_places=2,
                default=23,
                help_text="Declared value for customs",
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="description",
            field=models.TextField(
                default="some description", help_text="Package contents description"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="insurance_cost",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="insurance_required",
            field=models.BooleanField(
                default=False,
                help_text="Whether insurance is required for the shipment",
            ),
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="package_type",
            field=models.CharField(default="packge", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="recipient_country",
            field=models.CharField(default="PK", max_length=2),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="recipient_email",
            field=models.EmailField(default="mudasir@gmail.com", max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="recipient_name",
            field=models.CharField(default="name", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="recipient_phone",
            field=models.CharField(default="28938293829", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="sender_country",
            field=models.CharField(default="pk", max_length=2),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="sender_email",
            field=models.EmailField(default="mudasir@gmail.com", max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="sender_name",
            field=models.CharField(default="sldk", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="sender_phone",
            field=models.CharField(default="82398392", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="service_type",
            field=models.CharField(
                default="ecomnomy",
                help_text="e.g., Express, Standard, Economy",
                max_length=50,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="signature_required",
            field=models.BooleanField(
                default=False, help_text="Whether signature is required upon delivery"
            ),
        ),
        migrations.AddField(
            model_name="shipmentrequest",
            name="total_cost",
            field=models.DecimalField(
                decimal_places=2,
                default=25,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="shipmentrequest",
            name="dimensions",
            field=models.JSONField(
                default=dict,
                help_text='Format: {"length": 10, "width": 10, "height": 10} in cm',
            ),
        ),
        migrations.AlterField(
            model_name="shipmentrequest",
            name="weight",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
    ]
