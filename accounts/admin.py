# Register your models here.
import re

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import (City, Contact, DeliveryCommission, DriverPayment,
                     DriverProfile, Store, User, UserCountry)


class CustomUserCreationForm(UserCreationForm):
    """
    A form that creates a user with phone number as the primary identifier.
    """
    phone_number = forms.CharField(
        label=_("Phone number"),
        required=True,
        help_text=_("Required. Enter a valid phone number (digits only)."),
    )
    email = forms.EmailField(
        label=_("Email address"),
        required=False,
        help_text=_("Optional. Enter a valid email address."),
    )
    
    class Meta:
        model = User
        fields = ("phone_number", "email")
    
    def clean_phone_number(self):
        """
        Validate that the phone number contains only digits and is unique.
        """
        phone_number = self.cleaned_data.get('phone_number')
        
        # Check if phone number contains only digits
        if phone_number and not re.match(r'^\d+$', phone_number):
            raise forms.ValidationError(_("Phone number must contain only digits."))
            
        # Check if phone number is unique
        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError(_("A user with this phone number already exists."))
            
        return phone_number
    
    def save(self, commit=True):
        """
        Save the user and set the username to be the same as the phone number.
        """
        user = super().save(commit=False)
        user.username = self.cleaned_data.get('phone_number')
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """
    A form for updating users with phone number as the primary identifier.
    """
    class Meta:
        model = User
        fields = '__all__'
    
    def clean_phone_number(self):
        """
        Validate that the phone number contains only digits.
        """
        phone_number = self.cleaned_data.get('phone_number')
        
        if phone_number:
            # Check if phone number contains only digits
            if not re.match(r'^\d+$', phone_number):
                raise forms.ValidationError(_("Phone number must contain only digits."))
                
            # Check if phone number is unique (excluding the current user)
            if User.objects.exclude(pk=self.instance.pk).filter(phone_number=phone_number).exists():
                raise forms.ValidationError(_("A user with this phone number already exists."))
                
        return phone_number


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = ('id', 'phone_number', 'email', 'first_name', 'last_name', 'user_type', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'is_verified')
    search_fields = ('phone_number', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('phone_number', 'email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'address', 'country', 'default_shipping_method', 'preferred_currency')}),
        (_('Security'), {'fields': ('plain_password',), 'classes': ('collapse',), 'description': _('Passwords are stored in encrypted form and can be decrypted only when generating messages.')}),
        (_('Permissions'), {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Advanced options'), {'fields': ('username',), 'classes': ('collapse',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'email', 'password1', 'password2'),
        }),
    )
    
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'id')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('-created_at',)
    
@admin.register(UserCountry)
class UserCountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at', 'updated_at', 'id')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'code')
    ordering = ('-created_at',)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'status', 'created_at', 'id')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'phone', 'subject', 'message', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'email', 'phone', 'subject', 'message')
        }),
        (_('Admin'), {
            'fields': ('status', 'admin_notes')
        }),
        (_('Dates'), {
            'fields': ('created_at',)
        }),
    )
    ordering = ('-created_at',)

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'postal_code', 'delivery_charge', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'postal_code')
    readonly_fields = ('created_at', 'updated_at')
    fields = (
        'name', 'postal_code', 'delivery_charge', 'is_active',
        'created_at', 'updated_at'
    )

@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vehicle_type', 'is_active', 'total_deliveries', 'total_earnings')
    list_filter = ('is_active', 'vehicle_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'license_number')
    readonly_fields = ('total_earnings', 'total_deliveries', 'created_at', 'updated_at')
    filter_horizontal = ('cities',)
    
    # Combine all fields into a single fieldset
    fields = (
        'user', 'is_active', 'vehicle_type', 'license_number', 
        'cities', 'total_earnings', 'total_deliveries',
        'created_at', 'updated_at'
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter user selection to only show users with user_type='DRIVER'
        if db_field.name == 'user':
            kwargs['queryset'] = User.objects.filter(user_type='DRIVER')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(DeliveryCommission)
class DeliveryCommissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'delivery_type', 'reference_id', 'amount', 'earned_at')
    list_filter = ('delivery_type', 'earned_at')
    search_fields = ('driver__user__username', 'reference_id', 'description')
    readonly_fields = ('earned_at',)
    fieldsets = (
        (None, {'fields': ('driver', 'delivery_type', 'reference_id', 'amount')}),
        (_('Additional Information'), {'fields': ('description', 'earned_at')}),
    )

@admin.register(DriverPayment)
class DriverPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'payment_for', 'amount', 'payment_date')
    list_filter = ('payment_for', 'payment_date')
    search_fields = ('driver__user__username', 'payment_for', 'payment_id')
    readonly_fields = ('payment_date',)

