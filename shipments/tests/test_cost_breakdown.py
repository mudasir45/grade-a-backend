import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import City, User
from shipments.models import ShipmentExtras, ShipmentRequest
from shipping_rates.models import Country, Extras, ServiceType


class CostBreakdownTestCase(TestCase):
    """Test cases for cost breakdown functionality in shipment endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword',
            first_name='Test',
            last_name='User',
            phone_number='1234567890'
        )
        
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staffuser@example.com',
            password='staffpassword',
            first_name='Staff',
            last_name='User',
            phone_number='0987654321',
            is_staff=True
        )
        
        # Create test data
        self.departure_country = Country.objects.create(
            name='Test Departure',
            code='TD',
            country_type=Country.CountryType.DEPARTURE
        )
        
        self.destination_country = Country.objects.create(
            name='Test Destination',
            code='DS',
            country_type=Country.CountryType.DESTINATION
        )
        
        self.service_type = ServiceType.objects.create(
            name='Test Service',
            description='Test service description',
            delivery_time='1-2 days',
            price=Decimal('50.00')
        )
        
        # Create test city
        self.city = City.objects.create(
            name='Test City',
            delivery_charge=Decimal('50.00')
        )
        
        # Create extras
        self.extra1 = Extras.objects.create(
            name='Food Stuff',
            description='Food related items',
            charge_type=Extras.ChargeType.FIXED,
            value=Decimal('20.00')
        )
        
        self.extra2 = Extras.objects.create(
            name='Electronics',
            description='Electronic items',
            charge_type=Extras.ChargeType.FIXED,
            value=Decimal('30.00')
        )
        
        # Set up the client
        self.client = APIClient()
        
        # Base data for shipment creation
        self.shipment_data = {
            'sender_name': 'John Doe',
            'sender_email': 'john@example.com',
            'sender_phone': '1234567890',
            'sender_address': '123 Sender St',
            'sender_country': self.departure_country.id,
            
            'recipient_name': 'Jane Doe',
            'recipient_email': 'jane@example.com',
            'recipient_phone': '0987654321',
            'recipient_address': '456 Recipient St',
            'recipient_country': self.destination_country.id,
            'city': self.city.id,
            
            'package_type': 'Box',
            'weight': '5.00',
            'length': '10.00',
            'width': '10.00',
            'height': '10.00',
            'description': 'Test package',
            'declared_value': '100.00',
            
            'service_type': self.service_type.id,
            'insurance_required': False,
            'signature_required': True,
            'payment_method': 'ONLINE',
            'notes': 'Test notes'
        }
        
        # Cost breakdown data
        self.cost_breakdown = {
            'service_price': 50,
            'weight_charge': 25,
            'city_delivery_charge': 50,
            'additional_charges': [
                {
                    'name': 'fuel surcharge',
                    'type': 'Fixed Amount',
                    'value': 20,
                    'amount': 20,
                    'description': 'Fuel surcharge'
                }
            ],
            'extras': [
                {
                    'id': self.extra1.id,
                    'name': 'Food Stuff',
                    'charge_type': 'FIXED',
                    'value': 20,
                    'quantity': 2
                },
                {
                    'id': self.extra2.id,
                    'name': 'Electronics',
                    'charge_type': 'FIXED',
                    'value': 30,
                    'quantity': 1
                }
            ],
            'total_cost': 185
        }
    
    def test_create_shipment_with_cost_breakdown(self):
        """Test creating a shipment with cost breakdown"""
        # Authenticate as regular user
        self.client.force_authenticate(user=self.user)
        
        # Add cost breakdown to shipment data
        data = self.shipment_data.copy()
        data['cost_breakdown'] = self.cost_breakdown
        
        # Create shipment
        url = reverse('shipments:shipment-list-create')
        response = self.client.post(url, data, format='json')
        
        # Print response content for debugging
        print(f"\nTEST DEBUG - Create shipment response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Parse the response to extract required values
        response_data = json.loads(response.content.decode())
        
        # Get created shipment by unique fields since ID might not be in response
        # Use sender_email and recipient_email which should be unique in our test
        shipment = ShipmentRequest.objects.filter(
            sender_email=data['sender_email'],
            recipient_email=data['recipient_email']
        ).latest('created_at')
        
        # Check that cost fields were set correctly
        self.assertEqual(shipment.service_charge, Decimal('50.00'))
        self.assertEqual(shipment.weight_charge, Decimal('25.00'))
        self.assertEqual(shipment.delivery_charge, Decimal('50.00'))
        
        # Check extras were created correctly
        shipment_extras = ShipmentExtras.objects.filter(shipment=shipment)
        self.assertEqual(shipment_extras.count(), 2)
        
        # Check extras values
        extras_charges = sum(
            extra.extra.value * extra.quantity 
            for extra in shipment_extras
        )
        self.assertEqual(extras_charges, Decimal('70.00'))  # 20*2 + 30*1
        
        # Check total cost
        self.assertEqual(shipment.total_cost, Decimal('185.00'))
    
    def test_staff_create_shipment_with_cost_breakdown(self):
        """Test staff creating a shipment with cost breakdown for a user"""
        # Authenticate as staff user
        self.client.force_authenticate(user=self.staff_user)
        
        # Add cost breakdown to shipment data
        data = self.shipment_data.copy()
        data['cost_breakdown'] = self.cost_breakdown
        
        # Create shipment
        url = reverse('shipments:create-shipment', args=[self.user.id])
        response = self.client.post(url, data, format='json')
        
        # Print response content for debugging
        print(f"\nTEST DEBUG - Staff create shipment response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Parse the response to extract required values
        response_data = json.loads(response.content.decode())
        
        # Get created shipment by unique fields since ID might not be in response
        # Use sender_email and recipient_email which should be unique in our test
        shipment = ShipmentRequest.objects.filter(
            sender_email=data['sender_email'],
            recipient_email=data['recipient_email']
        ).latest('created_at')
        
        # Check that cost fields were set correctly
        self.assertEqual(shipment.service_charge, Decimal('50.00'))
        self.assertEqual(shipment.weight_charge, Decimal('25.00'))
        self.assertEqual(shipment.delivery_charge, Decimal('50.00'))
        
        # Check extras were created correctly
        shipment_extras = ShipmentExtras.objects.filter(shipment=shipment)
        self.assertEqual(shipment_extras.count(), 2)
        
        # Check total cost
        self.assertEqual(shipment.total_cost, Decimal('185.00'))
    
    def test_update_shipment_with_cost_breakdown(self):
        """Test updating a shipment with cost breakdown"""
        # Create a shipment first
        self.client.force_authenticate(user=self.user)
        data = self.shipment_data.copy()
        url = reverse('shipments:shipment-list-create')
        response = self.client.post(url, data, format='json')
        
        print(f"\nTEST DEBUG - Create shipment for update test response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Get created shipment by unique fields
        shipment = ShipmentRequest.objects.filter(
            sender_email=data['sender_email'],
            recipient_email=data['recipient_email']
        ).latest('created_at')
        
        # Now update with cost breakdown
        updated_cost_breakdown = self.cost_breakdown.copy()
        updated_cost_breakdown['service_price'] = 60
        updated_cost_breakdown['weight_charge'] = 30
        updated_cost_breakdown['total_cost'] = 200
        
        update_data = {
            'cost_breakdown': updated_cost_breakdown
        }
        
        update_url = reverse('shipments:shipment-detail', args=[shipment.id])
        response = self.client.patch(update_url, update_data, format='json')
        
        print(f"\nTEST DEBUG - Update shipment response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get updated shipment
        shipment.refresh_from_db()
        
        # Check that cost fields were updated correctly
        self.assertEqual(shipment.service_charge, Decimal('60.00'))
        self.assertEqual(shipment.weight_charge, Decimal('30.00'))
        
        # Check extras were created correctly
        shipment_extras = ShipmentExtras.objects.filter(shipment=shipment)
        self.assertEqual(shipment_extras.count(), 2)
        
        # Check total cost
        self.assertEqual(shipment.total_cost, Decimal('200.00'))
    
    def test_staff_update_shipment_with_cost_breakdown(self):
        """Test staff updating a shipment with cost breakdown"""
        # Create a shipment first
        self.client.force_authenticate(user=self.user)
        data = self.shipment_data.copy()
        url = reverse('shipments:shipment-list-create')
        response = self.client.post(url, data, format='json')
        
        print(f"\nTEST DEBUG - Create shipment for staff update test response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Get created shipment by unique fields
        shipment = ShipmentRequest.objects.filter(
            sender_email=data['sender_email'],
            recipient_email=data['recipient_email']
        ).latest('created_at')
        
        # Assign staff to the shipment
        shipment.staff = self.staff_user
        shipment.save()
        
        # Now authenticate as staff
        self.client.force_authenticate(user=self.staff_user)
        
        # Update with cost breakdown
        updated_cost_breakdown = self.cost_breakdown.copy()
        updated_cost_breakdown['service_price'] = 65
        updated_cost_breakdown['weight_charge'] = 35
        updated_cost_breakdown['total_cost'] = 210
        
        # Update extras - remove one, change quantity of the other
        updated_cost_breakdown['extras'] = [
            {
                'id': self.extra1.id,
                'name': 'Food Stuff',
                'charge_type': 'FIXED',
                'value': 20,
                'quantity': 3
            }
        ]
        
        update_data = {
            'cost_breakdown': updated_cost_breakdown
        }
        
        update_url = reverse('shipments:staff-shipment-management', args=[shipment.id])
        response = self.client.patch(update_url, update_data, format='json')
        
        print(f"\nTEST DEBUG - Staff update shipment response status: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get updated shipment
        shipment.refresh_from_db()
        
        # Check that cost fields were updated correctly
        self.assertEqual(shipment.service_charge, Decimal('65.00'))
        self.assertEqual(shipment.weight_charge, Decimal('35.00'))
        
        # Check extras were updated correctly
        shipment_extras = ShipmentExtras.objects.filter(shipment=shipment)
        self.assertEqual(shipment_extras.count(), 1)  # Only one extra now
        
        first_extra = shipment_extras.first()
        if first_extra:
            self.assertEqual(first_extra.quantity, 3)
        
        # Check total cost
        self.assertEqual(shipment.total_cost, Decimal('210.00')) 