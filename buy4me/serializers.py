from rest_framework import serializers

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
            'total_price', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class Buy4MeRequestSerializer(serializers.ModelSerializer):
    items = Buy4MeItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    staff = serializers.StringRelatedField(read_only=True)
    driver = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Buy4MeRequest
        fields = [
            'id', 'user', 'staff', 'driver', 'status', 'total_cost', 
            'shipping_address', 'notes', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'staff', 'driver', 'total_cost', 'created_at', 'updated_at']

class Buy4MeRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buy4MeRequest
        fields = ['shipping_address', 'notes', "id"] 