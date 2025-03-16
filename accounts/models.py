import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import (MaxValueValidator, MinValueValidator,
                                    RegexValidator)
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.utils import SixDigitIDMixin, generate_unique_id

# your_app/models.py

# Assume you have an implementation for generate_unique_id
def generate_unique_id(prefix):
    # Your implementation for generating a unique id, e.g. using uuid
    import uuid
    return f"{prefix}{uuid.uuid4().hex[:9].upper()}"

class CustomUserManager(UserManager):
    """
    Custom user manager that automatically sets username to phone_number if not provided.
    """
    def _create_user(self, username, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not username:
            if not extra_fields.get('phone_number'):
                raise ValueError('The phone_number field must be set')
            username = extra_fields.get('phone_number')
            
        email = self.normalize_email(email) if email else None
        username = self.model.normalize_username(username)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_user(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)
    
    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'SUPER_ADMIN')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self._create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser.
    The phone_number field is used as the primary identifier.
    """
    id = models.CharField(primary_key=True, max_length=12, editable=False)
    email = models.EmailField(_('email address'), blank=True, null=True)
    
    class UserType(models.TextChoices):
        WALK_IN = 'WALK_IN', _('Walk In')
        BUY4ME = 'BUY4ME', _('Buy4Me')
        DRIVER = 'DRIVER', _('Driver')
        ADMIN = 'ADMIN', _('Admin')
        SUPER_ADMIN = 'SUPER_ADMIN', _('Super Admin')
        
    class Currency(models.TextChoices):
        USD = 'USD', _('USD')
        EUR = 'EUR', _('EUR')
        GBP = 'GBP', _('GBP')
        CAD = 'CAD', _('CAD')
        AUD = 'AUD', _('AUD')
        
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.WALK_IN
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message='Phone number must contain only digits.',
                code='invalid_phone_number'
            )
        ],
        help_text=_("Phone number (digits only)")
    )
    address = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    country = models.ForeignKey('UserCountry', on_delete=models.SET_NULL, null=True, blank=True)
    default_shipping_method = models.ForeignKey(
        'shipping_rates.ServiceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_shipping_method'
    )
    preferred_currency = models.CharField(max_length=10, choices=Currency.choices, blank=True, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use the custom manager
    objects = CustomUserManager()

    # Set phone_number as the primary login field
    USERNAME_FIELD = 'phone_number'
    # No required fields other than the USERNAME_FIELD
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        if self.phone_number:
            return self.phone_number
        return self.username

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_unique_id('USR')
        
        # If phone number is provided but username is not, set username to phone number
        if self.phone_number and not self.username:
            self.username = self.phone_number
            
        super().save(*args, **kwargs)


class Store(SixDigitIDMixin, models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    url = models.URLField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Store')
        verbose_name_plural = _('Stores')

    def __str__(self):
        return self.name
    
class UserCountry(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User Country')
        verbose_name_plural = _('User Countries')

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.name

    
class Contact(SixDigitIDMixin, models.Model):
    """
    Model for storing contact form submissions
    """
    class ContactStatus(models.TextChoices):
        NEW = 'NEW', _('New')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        RESOLVED = 'RESOLVED', _('Resolved')
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ContactStatus.choices,
        default=ContactStatus.NEW
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"
    
class City(SixDigitIDMixin, models.Model):
    """
    Model for cities with delivery charges
    """
    name = models.CharField(
        max_length=100,
        help_text=_("Name of the city")
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_("Postal code (optional)")
    )
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_("Fixed delivery charge for this city")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this city is active for deliveries")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('City')
        verbose_name_plural = _('Cities')
        ordering = ['name']
        
    def __str__(self):
        if self.postal_code:
            return f"{self.name} ({self.postal_code})"
        return self.name

class DriverProfile(SixDigitIDMixin, models.Model):
    """
    Profile for drivers in the system
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_profile',
        help_text=_("User account associated with this driver profile")
    )
    vehicle_type = models.CharField(
        max_length=50,
        help_text=_("Type of vehicle used by the driver")
    )
    license_number = models.CharField(
        max_length=50,
        help_text=_("Driver's license number")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this driver is active and available for deliveries")
    )
    cities = models.ManyToManyField(
        City,
        related_name='drivers',
        blank=True,
        help_text=_("Cities this driver is assigned to")
    )
    total_deliveries = models.PositiveIntegerField(
        default=0,
        help_text=_("Total number of completed deliveries")
    )
    total_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Total earnings from all deliveries")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Driver Profile')
        verbose_name_plural = _('Driver Profiles')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Driver: {self.user.email}"
    
    def update_stats(self):
        """Update driver statistics"""
        # Count completed shipments
        from shipments.models import ShipmentRequest
        completed_shipments = ShipmentRequest.objects.filter(
            driver=self.user,
            status=ShipmentRequest.Status.DELIVERED
        ).count()
        
        # Count completed buy4me requests
        from buy4me.models import Buy4MeRequest
        completed_buy4me = Buy4MeRequest.objects.filter(
            driver=self.user,
            status=Buy4MeRequest.Status.COMPLETED
        ).count()
        
        # Update total deliveries
        self.total_deliveries = completed_shipments + completed_buy4me
        self.save(update_fields=['total_deliveries', 'updated_at'])

class DeliveryCommission(SixDigitIDMixin, models.Model):
    """
    Model for tracking individual delivery commissions for drivers
    """
    class DeliveryType(models.TextChoices):
        SHIPMENT = 'SHIPMENT', _('Shipment')
        BUY4ME = 'BUY4ME', _('Buy4Me')
    
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name='commissions',
        help_text=_("Driver who earned the commission")
    )
    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices,
        help_text=_("Type of delivery")
    )
    reference_id = models.CharField(
        max_length=50,
        help_text=_("ID of the related shipment or buy4me request")
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Commission amount")
    )
    earned_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the commission was earned")
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Description of the commission")
    )
    
    class Meta:
        verbose_name = _('Delivery Commission')
        verbose_name_plural = _('Delivery Commissions')
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.delivery_type} Commission: {self.amount} for {self.driver}"
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        # Update driver total earnings if this is a new commission
        if is_new:
            self.driver.total_earnings += self.amount
            self.driver.save(update_fields=['total_earnings', 'updated_at'])
    
    