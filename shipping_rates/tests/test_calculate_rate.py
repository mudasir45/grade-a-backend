from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import City
from shipping_rates.models import (AdditionalCharge, Country,
                                   DimensionalFactor, Extras, ServiceType,
                                   ShippingZone, WeightBasedRate)


class ShippingRateCalculatorViewTest(TestCase):
    """Test cases for the shipping rate calculator endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.url = reverse('shipping_rates:calculate-rate')
        
        # Create test countries
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
        
        # Create service type
        self.service_type = ServiceType.objects.create(
            name='Test Service',
            description='Test service description',
            delivery_time='1-2 days',
            price=Decimal('50.00')
        )
        
        # Create shipping zone
        self.shipping_zone = ShippingZone.objects.create(
            name='Test Zone'
        )
        self.shipping_zone.departure_countries.add(self.departure_country)
        self.shipping_zone.destination_countries.add(self.destination_country)
        
        # Create weight-based rate
        self.weight_rate = WeightBasedRate.objects.create(
            zone=self.shipping_zone,
            service_type=self.service_type,
            min_weight=Decimal('0.00'),
            max_weight=Decimal('100.00'),
            per_kg_rate=Decimal('5.00')
        )
        
        # Create dimensional factor
        self.dim_factor = DimensionalFactor.objects.create(
            service_type=self.service_type,
            factor=5000
        )
        
        # Create test city
        self.city = City.objects.create(
            name='Test City',
            delivery_charge=Decimal('20.00')
        )
        
        # Create additional charge
        self.additional_charge = AdditionalCharge.objects.create(
            name='Fuel Surcharge',
            description='Extra charge for fuel',
            charge_type=AdditionalCharge.ChargeType.FIXED,
            value=Decimal('10.00')
        )
        self.additional_charge.service_types.add(self.service_type)
        self.additional_charge.zones.add(self.shipping_zone)
        
        # Create extras
        self.extra = Extras.objects.create(
            name='Food Stuff',
            description='Food related items',
            charge_type=Extras.ChargeType.FIXED,
            value=Decimal('15.00')
        )
    
    def test_calculate_rate_with_weight_only(self):
        """Test rate calculation with weight only"""
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': 5.0
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cost_breakdown']['weight_charge'], 25.0)  # 5kg * $5/kg
        self.assertEqual(response.data['cost_breakdown']['service_price'], 50.0)
        self.assertEqual(len(response.data['cost_breakdown']['additional_charges']), 1)
        self.assertEqual(response.data['cost_breakdown']['total_cost'], 85.0)  # 50 + 25 + 10
    
    def test_calculate_rate_with_dimensions(self):
        """Test rate calculation with dimensions (volumetric weight)"""
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': 5.0,
            'length': 100,
            'width': 100,
            'height': 40
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Volumetric weight = 100*100*40/5000 = 80kg
        # Weight charge = 80kg * $5/kg = $400
        self.assertEqual(response.data['cost_breakdown']['weight_charge'], 400.0)
        self.assertEqual(response.data['cost_breakdown']['total_cost'], 460.0)  # 50 + 400 + 10
        
        # Verify rate details are included
        self.assertIn('rate_details', response.data)
        self.assertEqual(response.data['rate_details']['per_kg_rate'], 5.0)
    
    def test_calculate_rate_with_city(self):
        """Test rate calculation with city delivery charge"""
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': 5.0,
            'city': self.city.id
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cost_breakdown']['city_delivery_charge'], 20.0)
        self.assertEqual(response.data['cost_breakdown']['total_cost'], 105.0)  # 50 + 25 + 10 + 20
    
    def test_calculate_rate_with_extras(self):
        """Test rate calculation with extras"""
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': 5.0,
            'additional_charges': [
                {
                    'id': self.extra.id,
                    'quantity': 2
                }
            ]
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['cost_breakdown']['extras']), 1)
        self.assertEqual(response.data['cost_breakdown']['extras'][0]['quantity'], 2)
        self.assertEqual(response.data['cost_breakdown']['extras_total'], 30.0)  # 15 * 2
        self.assertEqual(response.data['cost_breakdown']['total_cost'], 115.0)  # 50 + 25 + 10 + 30
    
    def test_calculate_rate_with_invalid_data(self):
        """Test rate calculation with invalid data"""
        # Test with non-existent country (using a valid ID format but one that doesn't exist)
        payload = {
            'origin_country': 'CCC999999',  # Valid format but doesn't exist
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': 5.0
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('origin_country', response.data)
        
        # Test with missing required fields
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('service_type', response.data)
    
    def test_calculate_rate_with_dimensions_no_weight(self):
        """Test rate calculation with dimensions but no weight"""
        payload = {
            'origin_country': self.departure_country.id,
            'destination_country': self.destination_country.id,
            'service_type': self.service_type.id,
            'weight': None,  # No weight provided
            'length': 100,
            'width': 100,
            'height': 40
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Volumetric weight = 100*100*40/5000 = 80kg
        # Weight charge = 80kg * $5/kg = $400
        self.assertEqual(response.data['cost_breakdown']['weight_charge'], 400.0)
        self.assertEqual(response.data['cost_breakdown']['total_cost'], 460.0)  # 50 + 400 + 10
        
        # Verify rate details are included
        self.assertIn('rate_details', response.data)
        self.assertEqual(response.data['rate_details']['per_kg_rate'], 5.0) 