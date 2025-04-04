from rest_framework import serializers

from accounts.models import City

from .models import (AdditionalCharge, Country, Currency, DimensionalFactor,
                     Extras, ServiceType, ShippingZone, WeightBasedRate)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'country_type', 'is_active']

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'description', 'delivery_time', 'is_active']

class ShippingZoneSerializer(serializers.ModelSerializer):
    countries = CountrySerializer(many=True, read_only=True)
    
    class Meta:
        model = ShippingZone
        fields = ['id', 'name', 'countries', 'description', 'is_active']

class WeightBasedRateSerializer(serializers.ModelSerializer):
    zone = ShippingZoneSerializer(read_only=True)
    service_type = ServiceTypeSerializer(read_only=True)
    
    class Meta:
        model = WeightBasedRate
        fields = [
            'id', 'zone', 'service_type', 'min_weight', 'max_weight',
            'per_kg_rate', 'is_active'
        ]

class DimensionalFactorSerializer(serializers.ModelSerializer):
    service_type = ServiceTypeSerializer(read_only=True)
    
    class Meta:
        model = DimensionalFactor
        fields = ['id', 'service_type', 'factor', 'is_active']

class AdditionalChargeSerializer(serializers.ModelSerializer):
    zones = ShippingZoneSerializer(many=True, read_only=True)
    service_types = ServiceTypeSerializer(many=True, read_only=True)
    
    class Meta:
        model = AdditionalCharge
        fields = [
            'id', 'name', 'charge_type', 'value', 'zones',
            'service_types', 'is_active', 'description'
        ]

class ShippingCalculatorSerializer(serializers.Serializer):
    origin_country = serializers.CharField(
        required=True,
        max_length=9,
        help_text="9-letter country id for origin"
    )
    destination_country = serializers.CharField(
        required=True,
        max_length=9,
        help_text="9-letter country id for destination"
    )
    weight = serializers.DecimalField(
        required=False,
        max_digits=8, 
        decimal_places=2,
        help_text="Weight in kg",
        allow_null=True
    )
    length = serializers.DecimalField(
        required=False,
        max_digits=8, 
        decimal_places=2,
        help_text="Length in cm"
    )
    width = serializers.DecimalField(
        required=False,
        max_digits=8, 
        decimal_places=2,
        help_text="Width in cm"
    )
    height = serializers.DecimalField(
        required=False,
        max_digits=8, 
        decimal_places=2,
        help_text="Height in cm"
    )
    service_type = serializers.CharField(
        required=True,
        max_length=9,
        help_text="Service type id"
    )
    city = serializers.CharField(
        required=False,
        help_text="City id for delivery charges"
    )
    additional_charges = serializers.ListField(
        required=False,
        help_text="List of additional charges with quantities"
    )
    
    def validate(self, data):
        """
        Validate that countries exist and are of correct type, and that either weight or dimensions are provided
        """
        
        try:
            Country.objects.get(
                id=data['origin_country'],
                country_type=Country.CountryType.DEPARTURE,
                is_active=True
            )
        except Country.DoesNotExist:
            raise serializers.ValidationError(
                {"origin_country": "Invalid departure country code"}
            )

        try:
            Country.objects.get(
                id=data['destination_country'],
                country_type=Country.CountryType.DESTINATION,
                is_active=True
            )
        except Country.DoesNotExist:
            raise serializers.ValidationError(
                {"destination_country": "Invalid destination country code"}
            )
        
        try:
            ServiceType.objects.get(
                id=data['service_type'],
                is_active=True
            )
        except ServiceType.DoesNotExist:
            raise serializers.ValidationError({"service_type": "Invalid service type id"})
        
        # Check if dimensions are provided and valid
        has_valid_dimensions = all(
            data.get(key, 0) and float(data.get(key, 0)) > 0 
            for key in ['length', 'width', 'height']
        )
        
        # Check if weight is provided and valid
        weight = data.get('weight')
        has_valid_weight = weight is not None and float(weight) > 0
        
        # Either valid dimensions or valid weight must be provided
        if not has_valid_dimensions and not has_valid_weight:
            raise serializers.ValidationError(
                "Either valid weight (> 0) or valid dimensions (all > 0) must be provided"
            )
        
        return data
    
class ExtrasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Extras
        fields = ['id', 'name', 'description', 'charge_type',  'value', 'is_active']


class CurrencyConversionSerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=10)
    from_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    to_currency = serializers.CharField(max_length=10)

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'conversion_rate']

