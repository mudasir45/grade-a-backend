from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import City, DriverPayment, DriverProfile, User
from buy4me.models import Buy4MeRequest
from shipments.models import ShipmentRequest


class BulkDriverPaymentTests(APITestCase):
    def setUp(self):
        # Create test user with driver role
        self.user = User.objects.create_user(
            username='testdriver',
            email='testdriver@example.com',
            password='testpass123',
            user_type='DRIVER'
        )
        
        # Create driver profile
        self.driver_profile = DriverProfile.objects.create(
            user=self.user,
            vehicle_type='Car',
            license_number='DL12345'
        )
        
        # Create test city
        self.city = City.objects.create(
            name='Test City',
            delivery_charge=Decimal('10.00'),
            is_active=True
        )
        
        # Add city to driver's cities
        self.driver_profile.cities.add(self.city)
        
        # Create test Buy4Me requests
        self.buy4me_requests = []
        for i in range(3):
            request = Buy4MeRequest.objects.create(
                user=self.user,  # Owner is the same as driver for simplicity
                driver=self.user,
                city=self.city,
                shipping_address=f'Test Address {i}',
                notes=f'Test Notes {i}',
                city_delivery_charge=self.city.delivery_charge,
                total_cost=Decimal('50.00') + (i * Decimal('10.00'))  # Different amounts
            )
            self.buy4me_requests.append(request)
            
        # Create test Shipment requests
        self.shipment_requests = []
        for i in range(2):
            # This is simplified - in practice, you'll need to add more required fields
            shipment = ShipmentRequest.objects.create(
                user=self.user,
                driver=self.user,
                city=self.city,
                delivery_charge=Decimal('25.00') + (i * Decimal('5.00')),
                sender_name=f'Sender {i}',
                sender_phone='1234567890',
                sender_address=f'Sender Address {i}',
                recipient_name=f'Recipient {i}',
                recipient_phone='0987654321',
                recipient_address=f'Recipient Address {i}'
            )
            self.shipment_requests.append(shipment)
        
        # Setup API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # URL for bulk payments
        self.url = reverse('accounts:driver-bulk-payments')
    
    def test_buy4me_bulk_payment_creation(self):
        """Test creating bulk payments for Buy4Me requests"""
        # Request data
        data = {
            'payment_for': DriverPayment.PaymentFor.BUY4ME,
            'request_ids': [self.buy4me_requests[0].id, self.buy4me_requests[1].id]
        }
        
        # Make the request
        response = self.client.post(self.url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payments_created'], 2)
        
        # Verify payments were created
        payments = DriverPayment.objects.filter(
            driver=self.user,
            payment_for=DriverPayment.PaymentFor.BUY4ME,
            buy4me__in=[self.buy4me_requests[0], self.buy4me_requests[1]]
        )
        self.assertEqual(payments.count(), 2)
        
        # Verify payment amounts
        total_amount = sum(payment.amount for payment in payments)
        self.assertEqual(total_amount, Decimal('110.00'))  # 50 + 60
    
    def test_shipment_bulk_payment_creation(self):
        """Test creating bulk payments for Shipment requests"""
        # Request data
        data = {
            'payment_for': DriverPayment.PaymentFor.SHIPMENT,
            'request_ids': [self.shipment_requests[0].id, self.shipment_requests[1].id]
        }
        
        # Make the request
        response = self.client.post(self.url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payments_created'], 2)
        
        # Verify payments were created
        payments = DriverPayment.objects.filter(
            driver=self.user,
            payment_for=DriverPayment.PaymentFor.SHIPMENT,
            shipment__in=self.shipment_requests
        )
        self.assertEqual(payments.count(), 2)
        
        # Verify payment amounts
        total_amount = sum(payment.amount for payment in payments)
        self.assertEqual(total_amount, Decimal('55.00'))  # 25 + 30
    
    def test_bulk_payment_with_invalid_ids(self):
        """Test bulk payment with invalid request IDs"""
        # Request data with invalid IDs
        data = {
            'payment_for': DriverPayment.PaymentFor.BUY4ME,
            'request_ids': ['INVALID-ID-1', 'INVALID-ID-2']
        }
        
        # Make the request
        response = self.client.post(self.url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['payments_created'], 0)
        self.assertEqual(len(response.data['failed_requests']), 2)
    
    def test_bulk_payment_with_already_paid_requests(self):
        """Test bulk payment with requests that already have payments"""
        # Create a payment for the first buy4me request
        DriverPayment.objects.create(
            driver=self.user,
            payment_id='EXISTING-PAYMENT',
            amount=self.buy4me_requests[0].total_cost,
            payment_for=DriverPayment.PaymentFor.BUY4ME,
            buy4me=self.buy4me_requests[0]
        )
        
        # Request data including the already paid request
        data = {
            'payment_for': DriverPayment.PaymentFor.BUY4ME,
            'request_ids': [self.buy4me_requests[0].id, self.buy4me_requests[1].id]
        }
        
        # Make the request
        response = self.client.post(self.url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payments_created'], 1)  # Only one should be created
        
        # Verify only one new payment was created with an auto-generated payment_id
        new_payments = DriverPayment.objects.filter(
            buy4me=self.buy4me_requests[1], 
            payment_for=DriverPayment.PaymentFor.BUY4ME
        )
        self.assertEqual(new_payments.count(), 1)
        self.assertIsNotNone(new_payments.first().payment_id)  # Should have an auto-generated ID
