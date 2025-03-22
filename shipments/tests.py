from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shipping_rates.models import Country, Extras, ServiceType

from .models import ShipmentExtras, ShipmentRequest

User = get_user_model()

class ShipmentExtrasTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword',
            first_name='Test',
            last_name='User'
        )
        
        # Create test countries
        self.sender_country = Country.objects.create(
            name='Sender Country',
            code='SC',
            country_type='DEPARTURE'
        )
        
        self.recipient_country = Country.objects.create(
            name='Recipient Country',
            code='RC',
            country_type='DESTINATION'
        )
        
        # Create test service type
        self.service_type = ServiceType.objects.create(
            name='Test Service',
            description='Test service description',
            price=Decimal('10.00'),
            is_active=True
        )
        
        # Create test extras
        self.extra1 = Extras.objects.create(
            name='Extra 1',
            description='Test extra 1',
            charge_type='FIXED',
            value=Decimal('5.00'),
            is_active=True
        )
        
        self.extra2 = Extras.objects.create(
            name='Extra 2',
            description='Test extra 2',
            charge_type='PERCENTAGE',
            value=Decimal('10.00'),  # 10%
            is_active=True
        )
        
        # Create a shipment
        self.shipment = ShipmentRequest.objects.create(
            user=self.user,
            sender_name='Test Sender',
            sender_email='sender@example.com',
            sender_phone='1234567890',
            sender_address='Sender Address',
            sender_country=self.sender_country,
            recipient_name='Test Recipient',
            recipient_email='recipient@example.com',
            recipient_phone='0987654321',
            recipient_address='Recipient Address',
            recipient_country=self.recipient_country,
            package_type='Document',
            weight=Decimal('1.5'),
            length=Decimal('10'),
            width=Decimal('10'),
            height=Decimal('10'),
            description='Test package',
            declared_value=Decimal('100.00'),
            service_type=self.service_type,
            base_rate=Decimal('20.00'),
            per_kg_rate=Decimal('5.00'),
            weight_charge=Decimal('7.50'),
            service_charge=Decimal('10.00'),
            total_additional_charges=Decimal('0.00'),
            total_cost=Decimal('37.50')
        )
    
    def test_shipment_extras_creation(self):
        """Test creation of ShipmentExtras with quantities"""
        # Create shipment extras
        shipment_extra1 = ShipmentExtras.objects.create(
            shipment=self.shipment,
            extra=self.extra1,
            quantity=2
        )
        
        shipment_extra2 = ShipmentExtras.objects.create(
            shipment=self.shipment,
            extra=self.extra2,
            quantity=1
        )
        
        # Check if extras were created and associated with the shipment
        self.assertEqual(ShipmentExtras.objects.count(), 2)
        self.assertEqual(ShipmentExtras.objects.filter(shipment=self.shipment).count(), 2)
        
        # Check quantities
        self.assertEqual(shipment_extra1.quantity, 2)
        self.assertEqual(shipment_extra2.quantity, 1)
        
        # Check string representation
        self.assertIn(self.shipment.tracking_number, str(shipment_extra1))
        self.assertIn(self.extra1.name, str(shipment_extra1))
        self.assertIn('2', str(shipment_extra1))  # Check quantity is in string
