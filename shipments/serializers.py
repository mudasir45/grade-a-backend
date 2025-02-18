from rest_framework import serializers
from .models import ShipmentRequest, ShipmentTracking
from shipping_rates.models import ShippingZone, WeightBasedRate, DimensionalFactor, Country, ServiceType
from decimal import Decimal

class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentTracking
        fields = ['location', 'status', 'description']

class ShipmentRequestSerializer(serializers.ModelSerializer):
    tracking_updates = ShipmentTrackingSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    # dimensions = serializers.JSONField(required=True)

    class Meta:
        model = ShipmentRequest
        fields = '__all__'
        read_only_fields = [
            'user', 'tracking_number', 'status',
            'current_location', 'estimated_delivery',
            'tracking_history', 'base_rate', 'per_kg_rate',
            'weight_charge', 'total_additional_charges',
            'total_cost', 'created_at', 'updated_at'
        ]

    # def validate_dimensions(self, value):
    #     required_keys = ['length', 'width', 'height']
    #     if not all(key in value for key in required_keys):
    #         raise serializers.ValidationError(
    #             "Dimensions must include length, width, and height"
    #         )
    #     return value

class ShipmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentRequest
        fields = [
            'sender_name', 'sender_email', 'sender_phone',
            'sender_address', 'sender_country',
            'recipient_name', 'recipient_email', 'recipient_phone',
            'recipient_address', 'recipient_country',
            'package_type', 'weight', 'length', 'width', 'height',
            'description', 'declared_value',
            'service_type', 'insurance_required', 'signature_required',
            'notes'
        ]
        read_only_fields = [
            'tracking_number', 'status', 'current_location',
            'estimated_delivery', 'tracking_history',
            'base_rate', 'per_kg_rate', 'weight_charge',
            'total_additional_charges', 'total_cost'
        ]

    def calculate_shipping_rates(self, data):
        """Calculate shipping rates for the shipment"""
        try:
            # 1. Find applicable zone
            zone = ShippingZone.objects.filter(
                departure_countries=data['sender_country'],
                destination_countries=data['recipient_country'],
                is_active=True
            ).first()
            
            if not zone:
                raise serializers.ValidationError(
                    "No shipping zone found for this route"
                )
            
            # 2. Calculate volume and weights
            volume = data['length'] * data['width'] * data['height']
            
            # Get dimensional factor
            dim_factor = DimensionalFactor.objects.filter(
                service_type=data['service_type'],
                is_active=True
            ).first()
            
            # Calculate chargeable weight
            chargeable_weight = data['weight']
            if dim_factor:
                vol_weight = volume / dim_factor.factor
                chargeable_weight = max(data['weight'], vol_weight)
            
            # 3. Get applicable rate
            rate = WeightBasedRate.objects.filter(
                zone=zone,
                service_type=data['service_type'],
                min_weight__lte=chargeable_weight,
                max_weight__gte=chargeable_weight,
                is_active=True
            ).first()
            
            if not rate:
                raise serializers.ValidationError(
                    "No rate available for this weight and service type"
                )
            
            # 4. Calculate costs
            base_cost = rate.base_rate
            weight_charge = chargeable_weight * rate.per_kg_rate
            
            # 5. Get service charge from service type
            service_charge = data['service_type'].price
            
            # 6. Calculate additional charges
            total_additional = Decimal('0')
            for charge in zone.additionalcharge_set.filter(
                service_types=data['service_type'],
                is_active=True
            ):
                amount = (
                    charge.value if charge.charge_type == 'FIXED'
                    else (base_cost * charge.value / 100)
                )
                total_additional += amount
            
            # 7. Calculate total cost including service charge
            total_cost = (
                base_cost + 
                weight_charge + 
                service_charge + 
                total_additional
            )
            
            return {
                'base_rate': base_cost,
                'per_kg_rate': rate.per_kg_rate,
                'weight_charge': weight_charge,
                'service_charge': service_charge,
                'total_additional_charges': total_additional,
                'total_cost': total_cost
            }
            
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def create(self, validated_data):
        # Calculate shipping rates
        rates = self.calculate_shipping_rates(validated_data)
        
        # Update validated data with calculated rates
        validated_data.update(rates)
        
        return super().create(validated_data) 