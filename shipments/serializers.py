from decimal import Decimal

from rest_framework import serializers

from shipping_rates.models import (Country, DimensionalFactor, ServiceType,
                                   ShippingZone, WeightBasedRate)

from .models import ShipmentRequest, ShipmentStatusLocation


class ShipmentRequestSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    cod_amount = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=ShipmentRequest.PaymentMethod.choices)
    payment_status = serializers.ChoiceField(choices=ShipmentRequest.PaymentStatus.choices)

    class Meta:
        model = ShipmentRequest
        fields = '__all__'
        read_only_fields = [
            'user', 'tracking_number', 'status',
            'current_location', 'estimated_delivery',
            'tracking_history', 'base_rate', 'per_kg_rate',
            'weight_charge', 'total_additional_charges',
            'total_cost', 'created_at', 'updated_at',
            'cod_amount', 'payment_status', 'payment_date',
            'transaction_id'
        ]



class ShipmentCreateSerializer(serializers.ModelSerializer):
    payment_method = serializers.ChoiceField(
        choices=ShipmentRequest.PaymentMethod.choices,
        default=ShipmentRequest.PaymentMethod.ONLINE
    )

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
            'payment_method', 'notes'
        ]
        read_only_fields = [
            'tracking_number', 'status', 'current_location',
            'estimated_delivery', 'tracking_history',
            'base_rate', 'per_kg_rate', 'weight_charge',
            'total_additional_charges', 'total_cost',
            'cod_amount', 'payment_status', 'payment_date',
            'transaction_id'
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
            additional_charges = zone.additional_charges.filter(
                service_types=data['service_type'],
                is_active=True
            )
            for charge in additional_charges:
                amount = (
                    charge.value if charge.charge_type == 'FIXED'
                    else (base_cost * charge.value / 100)
                )
                total_additional += amount
            
            # 7. Calculate subtotal
            subtotal = (
                base_cost + 
                weight_charge + 
                service_charge + 
                total_additional
            )
            
            # 8. Add COD charge if applicable
            cod_amount = Decimal('0')
            if data.get('payment_method') == ShipmentRequest.PaymentMethod.COD:
                cod_amount = round(subtotal * Decimal('0.05'), 2)
            
            # 9. Calculate final total
            total_cost = subtotal + cod_amount
            
            return {
                'base_rate': base_cost,
                'per_kg_rate': rate.per_kg_rate,
                'weight_charge': weight_charge,
                'service_charge': service_charge,
                'total_additional_charges': total_additional,
                'cod_amount': cod_amount,
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


class ShipmentStatusLocationSerializer(serializers.ModelSerializer):
    """Serializer for ShipmentStatusLocation model"""
    status_type_display = serializers.CharField(source='get_status_type_display', read_only=True)
    
    class Meta:
        model = ShipmentStatusLocation
        fields = [
            'id', 'status_type', 'status_type_display', 
            'location_name', 'description', 'display_order'
        ]
        read_only_fields = ['id', 'status_type_display']


class StatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating shipment status"""
    status_location_id = serializers.IntegerField(
        required=True,
        help_text="ID of the status location to use for the update"
    )
    custom_description = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Optional custom description to override the default"
    )
    
    def validate_status_location_id(self, value):
        """Validate that the status location exists and is active"""
        try:
            status_location = ShipmentStatusLocation.objects.get(id=value, is_active=True)
            # Store the status location for later use
            self.context['status_location'] = status_location
            return value
        except ShipmentStatusLocation.DoesNotExist:
            raise serializers.ValidationError(
                "Status location not found or is inactive"
            )
    
    def update(self, instance, validated_data):
        """Update the shipment status"""
        status_location = self.context['status_location']
        custom_description = validated_data.get('custom_description')
        
        # Get the corresponding ShipmentRequest.Status
        status_mapping = ShipmentStatusLocation.get_status_mapping()
        shipment_status = status_mapping.get(status_location.status_type)
        
        # Use custom description if provided, otherwise use the default
        description = custom_description if custom_description else status_location.description
        
        # Update the tracking information
        instance.update_tracking(
            shipment_status,
            status_location.location_name,
            description
        )
        
        return instance 