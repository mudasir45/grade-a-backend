from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import (City, Contact, DeliveryCommission, DriverProfile,
                             Store, UserCountry)

User = get_user_model()


class UserCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCountry
        fields = ('id', 'name', 'code')
        
        


class UserSerializer(serializers.ModelSerializer):
    country_details = UserCountrySerializer(source='country', read_only=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'address', 'user_type', 'is_verified', 'country', 'preferred_currency',
            'date_joined', 'country_details', 'default_shipping_method'
        )
        read_only_fields = ('id', 'date_joined', 'is_verified', 'country_details')

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = (
            'email', 'username', 'password', 'first_name', 'last_name',
            'phone_number', 'address', 'user_type', 'country', 'preferred_currency'
        )
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class ContactSerializer(serializers.ModelSerializer):
    """
    Serializer for the Contact model
    """
    class Meta:
        model = Contact
        fields = ['id', 'name', 'email', 'phone', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
        
    def create(self, validated_data):
        contact = Contact.objects.create(**validated_data)
        return contact

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'postal_code', 'delivery_charge', 'is_active')


class DriverProfileSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_deliveries = serializers.IntegerField(read_only=True)
    cities = CitySerializer(many=True, read_only=True)
    
    class Meta:
        model = DriverProfile
        fields = (
            'id', 'user', 'user_details', 'vehicle_type', 'license_number',
            'is_active', 'cities', 'total_earnings',
            'total_deliveries', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'total_earnings', 'total_deliveries', 'created_at', 'updated_at')


class DriverProfileCreateSerializer(serializers.ModelSerializer):
    cities = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True),
        many=True,
        required=False
    )
    
    class Meta:
        model = DriverProfile
        fields = (
            'user', 'vehicle_type', 'license_number',
            'is_active', 'cities'
        )
    
    def validate_user(self, value):
        """Ensure the user is of type DRIVER"""
        if value.user_type != 'DRIVER':
            raise serializers.ValidationError("User must be of type DRIVER")
        
        # Check if driver profile already exists
        if DriverProfile.objects.filter(user=value).exists():
            raise serializers.ValidationError("Driver profile already exists for this user")
        
        return value


class DeliveryCommissionSerializer(serializers.ModelSerializer):
    driver_details = serializers.StringRelatedField(source='driver', read_only=True)
    
    class Meta:
        model = DeliveryCommission
        fields = (
            'id', 'driver', 'driver_details', 'delivery_type', 'reference_id',
            'amount', 'earned_at', 'description'
        )
        read_only_fields = ('id', 'earned_at')
    

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = "__all__"
        

