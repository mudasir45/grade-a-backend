from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import City, User
from buy4me.models import Buy4MeItem, Buy4MeRequest


class Buy4MeModelTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test city
        self.city = City.objects.create(
            name='Test City',
            delivery_charge=Decimal('10.00'),
            is_active=True
        )
        
        # Create test request
        self.request = Buy4MeRequest.objects.create(
            user=self.user,
            city=self.city,
            shipping_address='Test Address',
            notes='Test Notes'
        )

    def test_buy4me_request_creation(self):
        """Test Buy4MeRequest model creation and basic attributes"""
        self.assertEqual(self.request.user, self.user)
        self.assertEqual(self.request.city, self.city)
        self.assertEqual(self.request.status, Buy4MeRequest.Status.DRAFT)
        self.assertEqual(self.request.total_cost, Decimal('0.00'))
        self.assertEqual(self.request.city_delivery_charge, self.city.delivery_charge)

    def test_buy4me_item_creation(self):
        """Test Buy4MeItem model creation and price calculations"""
        item = Buy4MeItem.objects.create(
            buy4me_request=self.request,
            product_name='Test Product',
            product_url='https://example.com/product',
            quantity=2,
            unit_price=Decimal('50.00'),
            store_to_warehouse_delivery_charge=Decimal('5.00')
        )
        
        # Test item price calculations
        self.assertEqual(item.total_price, Decimal('100.00'))  # 2 * 50
        
        # Test request total cost calculation
        self.request.calculate_total_cost()
        self.assertEqual(self.request.total_cost, Decimal('115.00'))  # (2*50) + 5 + 10 (city delivery)

    def test_multiple_items_total_cost(self):
        """Test total cost calculation with multiple items"""
        # Create multiple items
        Buy4MeItem.objects.create(
            buy4me_request=self.request,
            product_name='Product 1',
            product_url='https://example.com/product1',
            quantity=2,
            unit_price=Decimal('50.00'),
            store_to_warehouse_delivery_charge=Decimal('5.00')
        )
        
        Buy4MeItem.objects.create(
            buy4me_request=self.request,
            product_name='Product 2',
            product_url='https://example.com/product2',
            quantity=1,
            unit_price=Decimal('30.00'),
            store_to_warehouse_delivery_charge=Decimal('3.00')
        )
        
        # Calculate total cost
        self.request.calculate_total_cost()
        
        # Expected total:
        # Product 1: (2 * 50) = 100, store-to-warehouse: 5
        # Product 2: (1 * 30) = 30, store-to-warehouse: 3
        # City delivery: 10
        # Total: 100 + 5 + 30 + 3 + 10 = 148
        self.assertEqual(self.request.total_cost, Decimal('148.00'))


class Buy4MeAPITests(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test city
        self.city = City.objects.create(
            name='Test City',
            delivery_charge=Decimal('10.00'),
            is_active=True
        )
        
        # Create test request
        self.request = Buy4MeRequest.objects.create(
            user=self.user,
            city=self.city,
            shipping_address='Test Address',
            notes='Test Notes'
        )
        
        # Create test item
        self.item = Buy4MeItem.objects.create(
            buy4me_request=self.request,
            product_name='Test Product',
            product_url='https://example.com/product',
            quantity=2,
            unit_price=Decimal('50.00'),
            store_to_warehouse_delivery_charge=Decimal('5.00')
        )
        
        # Setup API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_active_request(self):
        """Test getting active (draft) request"""
        url = reverse('buy4me:active-request')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.request.id)
        self.assertEqual(response.data['status'], Buy4MeRequest.Status.DRAFT)

    def test_create_buy4me_request(self):
        """Test creating a new Buy4Me request"""
        url = reverse('buy4me:buy4me-request-list')
        data = {
            'shipping_address': 'New Test Address',
            'notes': 'New Test Notes'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['shipping_address'], data['shipping_address'])
        self.assertEqual(response.data['notes'], data['notes'])
        # Status might not be included in the response due to CreateSerializer
        # We'll retrieve the request to check the status
        request_id = response.data['id']
        created_request = Buy4MeRequest.objects.get(id=request_id)
        self.assertEqual(created_request.status, Buy4MeRequest.Status.DRAFT)

    def test_create_buy4me_request_with_city(self):
        """Test creating a new Buy4Me request with a city"""
        url = reverse('buy4me:buy4me-request-list')
        data = {
            'shipping_address': 'New Test Address',
            'notes': 'New Test Notes',
            'city': self.city.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['shipping_address'], data['shipping_address'])
        self.assertEqual(response.data['notes'], data['notes'])
        
        # Get the created request
        request_id = response.data['id']
        created_request = Buy4MeRequest.objects.get(id=request_id)
        
        # Check that city and city_delivery_charge were set correctly
        self.assertEqual(created_request.city.id, self.city.id)
        self.assertEqual(created_request.city_delivery_charge, self.city.delivery_charge)
        
        # Check that total_cost was calculated correctly (no items yet, so just city_delivery_charge)
        self.assertEqual(created_request.total_cost, self.city.delivery_charge)

    def test_add_item_to_request(self):
        """Test adding an item to a Buy4Me request"""
        url = reverse('buy4me:buy4me-item-list', kwargs={'request_pk': self.request.id})
        data = {
            'product_name': 'New Product',
            'product_url': 'https://example.com/new-product',
            'quantity': 3,
            'unit_price': '40.00',
            'store_to_warehouse_delivery_charge': '4.00',
            'currency': 'USD'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['product_name'], data['product_name'])
        self.assertEqual(response.data['quantity'], data['quantity'])
        
        # Verify total cost was updated
        self.request.refresh_from_db()
        self.request.calculate_total_cost()
        # Expected: (2*50) + 5 + (3*40) + 4 + 10 = 100 + 5 + 120 + 4 + 10 = 239
        self.assertEqual(self.request.total_cost, Decimal('239.00'))

    def test_update_request_status(self):
        """Test updating request status"""
        url = reverse('buy4me:buy4me-request-update-status', kwargs={'pk': self.request.id})
        data = {'status': Buy4MeRequest.Status.SUBMITTED}
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Buy4MeRequest.Status.SUBMITTED)

    def test_unauthorized_access(self):
        """Test unauthorized access to Buy4Me endpoints"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        # Create request for other user
        other_request = Buy4MeRequest.objects.create(
            user=other_user,
            city=self.city,
            shipping_address='Other Address'
        )
        
        # Try to access other user's request
        url = reverse('buy4me:buy4me-request-detail', kwargs={'pk': other_request.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_item(self):
        """Test deleting an item from a request"""
        url = reverse('buy4me:buy4me-item-detail', kwargs={
            'request_pk': self.request.id,
            'pk': self.item.id
        })
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify item was deleted and total cost was updated
        self.assertFalse(Buy4MeItem.objects.filter(id=self.item.id).exists())
        self.request.refresh_from_db()
        self.request.calculate_total_cost()
        self.assertEqual(self.request.total_cost, Decimal('10.00'))  # Only city delivery charge

    def test_update_item(self):
        """Test updating an item in a request"""
        url = reverse('buy4me:buy4me-item-detail', kwargs={
            'request_pk': self.request.id,
            'pk': self.item.id
        })
        data = {
            'quantity': 3,
            'unit_price': '45.00'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity'], data['quantity'])
        self.assertEqual(response.data['unit_price'], data['unit_price'])
        
        # Verify total cost was updated
        self.request.refresh_from_db()
        self.request.calculate_total_cost()
        # Expected: (3*45) + 5 + 10 = 135 + 5 + 10 = 150
        self.assertEqual(self.request.total_cost, Decimal('150.00'))

    def test_request_validation(self):
        """Test request validation rules"""
        # Try to create request without required fields
        url = reverse('buy4me:buy4me-request-list')
        data = {
            'notes': 'Test Notes'  # Missing shipping_address
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_validation(self):
        """Test item validation rules"""
        url = reverse('buy4me:buy4me-item-list', kwargs={'request_pk': self.request.id})
        # Try with a negative price instead of invalid quantity
        data = {
            'product_name': 'Test Product',
            'product_url': 'https://example.com/product',
            'quantity': 1,
            'unit_price': '-50.00'  # Negative price
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_item_recalculates_request_total(self):
        """Test that updating an item automatically recalculates the request's total cost"""
        # Initial state - we know from previous tests this request has:
        # - 1 item with quantity=2, unit_price=50.00, store_to_warehouse_delivery_charge=5.00
        # - city_delivery_charge=10.00
        # - total_cost = (2*50) + 5 + 10 = 115.00
        self.assertEqual(self.request.total_cost, Decimal('0.00'))  # Initially not calculated
        self.request.calculate_total_cost()
        self.assertEqual(self.request.total_cost, Decimal('115.00'))
        
        # Update the item
        url = reverse('buy4me:buy4me-item-detail', kwargs={
            'request_pk': self.request.id,
            'pk': self.item.id
        })
        
        # First, update quantity
        data = {'quantity': 3}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify request total was automatically updated 
        # New calculation: (3*50) + 5 + 10 = 150 + 5 + 10 = 165
        self.request.refresh_from_db()
        self.assertEqual(self.request.total_cost, Decimal('165.00'))
        
        # Now update unit_price
        data = {'unit_price': '60.00'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify request total was automatically updated again
        # New calculation: (3*60) + 5 + 10 = 180 + 5 + 10 = 195
        self.request.refresh_from_db()
        self.assertEqual(self.request.total_cost, Decimal('195.00'))
        
        # Update store_to_warehouse_delivery_charge
        data = {'store_to_warehouse_delivery_charge': '15.00'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify request total was automatically updated
        # New calculation: (3*60) + 15 + 10 = 180 + 15 + 10 = 205
        self.request.refresh_from_db()
        self.assertEqual(self.request.total_cost, Decimal('205.00'))

    def test_update_buy4me_request_with_city(self):
        """Test updating a Buy4Me request with a new city"""
        # Create a new city with different delivery charge
        new_city = City.objects.create(
            name='New City',
            delivery_charge=Decimal('15.00'),
            is_active=True
        )
        
        # Create a request without city first
        request_without_city = Buy4MeRequest.objects.create(
            user=self.user,
            shipping_address='Address Without City',
            notes='Notes Without City'
        )
        self.assertIsNone(request_without_city.city)
        self.assertEqual(request_without_city.city_delivery_charge, Decimal('0.00'))
        
        # Update the request with a city
        url = reverse('buy4me:buy4me-request-detail', kwargs={'pk': request_without_city.id})
        data = {
            'city': new_city.id
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh from database and check city was set
        request_without_city.refresh_from_db()
        self.assertEqual(request_without_city.city.id, new_city.id)
        self.assertEqual(request_without_city.city_delivery_charge, new_city.delivery_charge)
        self.assertEqual(request_without_city.total_cost, new_city.delivery_charge)
        
        # Now update the request with another city
        data = {
            'city': self.city.id
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh from database and check city was updated
        request_without_city.refresh_from_db()
        self.assertEqual(request_without_city.city.id, self.city.id)
        self.assertEqual(request_without_city.city_delivery_charge, self.city.delivery_charge)
        self.assertEqual(request_without_city.total_cost, self.city.delivery_charge)
