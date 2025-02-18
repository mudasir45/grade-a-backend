from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'address', 'user_type', 'is_verified',
            'date_joined'
        )
        read_only_fields = ('id', 'date_joined', 'is_verified')

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'username', 'password', 'first_name', 'last_name',
            'phone_number', 'address', 'user_type', 'country'
        )

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user 