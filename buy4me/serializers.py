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

class Buy4MeRequestSerializer(serializers.ModelSerializer):
    items = Buy4MeItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    staff = serializers.StringRelatedField(read_only=True)
    driver = serializers.StringRelatedField(read_only=True)
    city = CitySerializer(read_only=True)
    
    class Meta:
        model = Buy4MeRequest
        fields = [
            'id', 'user', 'staff', 'driver', 'city', 'status', 'total_cost', 
            'city_delivery_charge', 'shipping_address', 'notes', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'staff', 'driver', 'city', 'total_cost', 
            'city_delivery_charge', 'created_at', 'updated_at'
        ]

class Buy4MeRequestCreateSerializer(serializers.ModelSerializer):
    city = serializers.PrimaryKeyRelatedField(
        queryset=apps.get_model('accounts', 'City').objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Buy4MeRequest
        fields = ['shipping_address', 'notes', 'city', 'id']

class Buy4MeRequestUpdateSerializer(serializers.ModelSerializer):
    city = serializers.PrimaryKeyRelatedField(
        queryset=apps.get_model('accounts', 'City').objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Buy4MeRequest
        fields = ['shipping_address', 'notes', 'city', 'status']
        extra_kwargs = {'status': {'required': False}} 