from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import Contact, UserCountry

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
    
