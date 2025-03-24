from decimal import Decimal

from django.test import TestCase

from accounts.models import City
from shipments.utils import calculate_shipping_cost
from shipping_rates.models import (AdditionalCharge, Country,
                                   DimensionalFactor, Extras, ServiceType,
                                   ShippingZone, WeightBasedRate)


class CalculateShippingCostTest(TestCase):
    """Test cases for calculating shipping costs"""
    
    def setUp(self):
        """Set up test data"""
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
            max_weight=Decimal('10.00'),
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
    
    def test_calculate_basic_shipping_cost(self):
        """Test basic shipping cost calculation with weight only"""
        result = calculate_shipping_cost(
            sender_country_id=self.departure_country.id,
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id,
            weight=5.0
        )
        
        self.assertEqual(result['service_price'], Decimal('50.00'))
        self.assertEqual(result['weight_charge'], Decimal('25.00'))  # 5kg * $5/kg
        self.assertEqual(len(result['additional_charges']), 1)
        self.assertEqual(result['total_cost'], Decimal('85.00'))  # 50 + 25 + 10
        self.assertEqual(len(result['errors']), 0)
    
    def test_calculate_shipping_cost_with_city(self):
        """Test shipping cost calculation with city delivery charge"""
        result = calculate_shipping_cost(
            sender_country_id=self.departure_country.id,
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id,
            weight=5.0,
            city_id=self.city.id
        )
        
        self.assertEqual(result['city_delivery_charge'], Decimal('20.00'))
        self.assertEqual(result['total_cost'], Decimal('105.00'))  # 50 + 25 + 10 + 20
    
    def test_calculate_shipping_cost_with_dimensions(self):
        """Test shipping cost calculation with dimensions (volumetric weight)"""
        # Make our test more robust by extending the weight range
        self.weight_rate.max_weight = Decimal('100.00')
        self.weight_rate.save()
        
        # Create dimensions that result in volumetric weight of 8kg
        # 100 * 100 * 40 = 400,000 / 5000 = 80kg (which is greater than actual weight of 5kg)
        dimensions = {
            'length': 100,
            'width': 100, 
            'height': 40
        }
        
        result = calculate_shipping_cost(
            sender_country_id=self.departure_country.id,
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id,
            weight=5.0,
            dimensions=dimensions
        )
        
        # Print debug info
        print("\nDEBUG: Volumetric weight calculation")
        print(f"Result: {result}")
        
        if 'volumetric' in result:
            print(f"Volumetric details: {result['volumetric']}")
        
        # Should use volumetric weight (80kg) instead of actual weight (5kg)
        # Weight charge = 80kg * $5/kg = $400
        self.assertEqual(result['weight_charge'], Decimal('400.00'))
        self.assertEqual(result['total_cost'], Decimal('460.00'))  # 50 + 400 + 10
    
    def test_calculate_shipping_cost_with_extras(self):
        """Test shipping cost calculation with extras"""
        extras_data = [
            {
                'id': self.extra.id,
                'quantity': 2
            }
        ]
        
        result = calculate_shipping_cost(
            sender_country_id=self.departure_country.id,
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id,
            weight=5.0,
            extras_data=extras_data
        )
        
        self.assertEqual(len(result['extras']), 1)
        self.assertEqual(result['extras'][0]['quantity'], 2)
        self.assertEqual(result['extras_total'], Decimal('30.00'))  # 15 * 2
        self.assertEqual(result['total_cost'], Decimal('115.00'))  # 50 + 25 + 10 + 30
    
    def test_calculate_shipping_cost_with_invalid_data(self):
        """Test shipping cost calculation with invalid data"""
        # Test with non-existent country
        result = calculate_shipping_cost(
            sender_country_id='invalid_id',
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id,
            weight=5.0
        )
        
        self.assertTrue(len(result['errors']) > 0)
        self.assertIn("countries not found", result['errors'][0])
        
        # Test with missing weight and dimensions
        result = calculate_shipping_cost(
            sender_country_id=self.departure_country.id,
            recipient_country_id=self.destination_country.id,
            service_type_id=self.service_type.id
        )
        
        self.assertTrue(len(result['errors']) > 0)
        self.assertIn("Missing required parameters", result['errors'][0]) 