import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import (City, Contact, DeliveryCommission, DriverPayment,
                             DriverProfile, Store, UserCountry)

User = get_user_model()

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class PhoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer that uses phone_number for authentication instead of username.
    """
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate_phone_number(self, value):
        """Validate that the phone number contains only digits"""
        if not re.match(r'^\d+$', value):
            raise serializers.ValidationError("Phone number must contain only digits.")
        return value
    
    def validate(self, attrs):
        # The authenticate call simply passes the phone_number as username
        authenticate_kwargs = {
            'phone_number': attrs.get('phone_number'),
            'password': attrs.get('password')
        }
        
        try:
            authenticate_kwargs['request'] = self.context['request']
        except KeyError:
            pass
        
        # Authenticate the user
        user = authenticate(**authenticate_kwargs)
        
        if not user:
            raise serializers.ValidationError('No active account found with the given credentials')
        
        # Get the token
        refresh = self.get_token(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }
        
        return data

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
    phone_number = serializers.CharField(required=True)
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    
    class Meta:
        model = User
        fields = (
            'email', 'username', 'password', 'first_name', 'last_name',
            'phone_number', 'address', 'user_type', 'country', 'preferred_currency'
        )
    
    def validate_phone_number(self, value):
        """Validate that the phone number is unique and contains only digits"""
        # Check if phone number contains only digits
        if not re.match(r'^\d+$', value):
            raise serializers.ValidationError("Phone number must contain only digits.")
            
        # Check if phone number is unique
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        
        # If username is not provided, use phone number as username
        if 'username' not in validated_data or not validated_data['username']:
            validated_data['username'] = validated_data['phone_number']
            
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
        


class DriverPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverPayment
        fields = '__all__'

