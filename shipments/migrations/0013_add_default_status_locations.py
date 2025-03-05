from django.db import migrations


def add_default_status_locations(apps, schema_editor):
    """
    Add default status locations for shipment tracking
    """
    ShipmentStatusLocation = apps.get_model('shipments', 'ShipmentStatusLocation')
    
    # Define default status locations
    default_locations = [
        # PENDING
        {
            'status_type': 'PENDING',
            'location_name': 'Order Received',
            'description': 'Shipment request created',
            'display_order': 10,
        },
        
        # PROCESSING
        {
            'status_type': 'PROCESSING',
            'location_name': 'Processing Center',
            'description': 'Shipment is being processed',
            'display_order': 20,
        },
        
        # PICKED_UP
        {
            'status_type': 'PICKED_UP',
            'location_name': 'Pickup Location',
            'description': 'Package picked up from sender',
            'display_order': 30,
        },
        {
            'status_type': 'PICKED_UP',
            'location_name': 'Sender Address',
            'description': 'Package collected from sender address',
            'display_order': 31,
        },
        
        # IN_TRANSIT
        {
            'status_type': 'IN_TRANSIT',
            'location_name': 'Origin Sorting Center',
            'description': 'Package arrived at origin sorting center',
            'display_order': 40,
        },
        {
            'status_type': 'IN_TRANSIT',
            'location_name': 'In Transit',
            'description': 'Package in transit to destination',
            'display_order': 41,
        },
        {
            'status_type': 'IN_TRANSIT',
            'location_name': 'Destination Sorting Center',
            'description': 'Package arrived at destination sorting center',
            'display_order': 42,
        },
        
        # OUT_FOR_DELIVERY
        {
            'status_type': 'OUT_FOR_DELIVERY',
            'location_name': 'Local Delivery Center',
            'description': 'Package at local delivery center',
            'display_order': 50,
        },
        {
            'status_type': 'OUT_FOR_DELIVERY',
            'location_name': 'Destination City',
            'description': 'Out for delivery',
            'display_order': 51,
        },
        
        # DELIVERED
        {
            'status_type': 'DELIVERED',
            'location_name': 'Recipient Address',
            'description': 'Package delivered to recipient',
            'display_order': 60,
        },
        {
            'status_type': 'DELIVERED',
            'location_name': 'Pickup Point',
            'description': 'Package delivered to pickup point',
            'display_order': 61,
        },
        
        # CANCELLED
        {
            'status_type': 'CANCELLED',
            'location_name': 'Cancelled',
            'description': 'Shipment has been cancelled',
            'display_order': 70,
        },
    ]
    
    # Create the default locations
    for location_data in default_locations:
        ShipmentStatusLocation.objects.create(**location_data)


def remove_default_status_locations(apps, schema_editor):
    """
    Remove default status locations
    """
    ShipmentStatusLocation = apps.get_model('shipments', 'ShipmentStatusLocation')
    ShipmentStatusLocation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0013_shipmentstatuslocation'),
    ]

    operations = [
        migrations.RunPython(
            add_default_status_locations,
            remove_default_status_locations
        ),
    ] 