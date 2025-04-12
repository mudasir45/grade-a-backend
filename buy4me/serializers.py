from django.apps import apps
from rest_framework import serializers

from accounts.serializers import CitySerializer

from .models import Buy4MeItem, Buy4MeRequest


class Buy4MeItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Buy4MeItem
        fields = [
            'id', 'product_name', 'product_url', 'quantity',
            'color', 'size', 'unit_price', 'currency', 'notes',
            'store_to_warehouse_delivery_charge', 'total_price', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class Buy4MeItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buy4MeItem
        fields = ['product_name', 'product_url', 'quantity', 'color', 'size', 
                 'unit_price', 'currency', 'notes', 'store_to_warehouse_delivery_charge']

class Buy4MeRequestSerializer(serializers.ModelSerializer):
    items = Buy4MeItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    staff = serializers.StringRelatedField(read_only=True)
    driver = serializers.StringRelatedField(read_only=True)
    status = serializers.ChoiceField(choices=Buy4MeRequest.Status.choices)
    payment_status = serializers.ChoiceField(choices=Buy4MeRequest.PaymentStatus.choices)

    class Meta:
        model = Buy4MeRequest
        fields = [
            'id', 'user', 'staff', 'driver', 'status', 'payment_status',
            'service_fee', 'service_fee_percentage', 'total_cost', 'shipping_address', 'notes', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'staff', 'driver', 'service_fee', 'service_fee_percentage', 'total_cost', 'created_at', 'updated_at']

class Buy4MeRequestCreateSerializer(serializers.ModelSerializer):
    items = Buy4MeItemCreateSerializer(many=True)
    status = serializers.ChoiceField(choices=Buy4MeRequest.Status.choices, default=Buy4MeRequest.Status.DRAFT)
    payment_status = serializers.ChoiceField(choices=Buy4MeRequest.PaymentStatus.choices, default=Buy4MeRequest.PaymentStatus.PENDING)

    class Meta:
        model = Buy4MeRequest
        fields = [
            'id', 'status', 'payment_status', 'shipping_address', 'notes', 'items'
        ]
        read_only_fields = ['id']

class Buy4MeRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buy4MeRequest
        fields = ['shipping_address', 'notes', 'status', 'payment_status']
        extra_kwargs = {
            'status': {'required': False},
            'payment_status': {'required': False}
        } 