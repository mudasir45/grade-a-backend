from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.utils import SixDigitIDMixin


class Buy4MeRequest(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SUBMITTED = 'SUBMITTED', _('Submitted')
        ORDER_PLACED = 'ORDER_PLACED', _('Order Placed')
        IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
        WAREHOUSE_ARRIVED = 'WAREHOUSE_ARRIVED', _('Warehouse Arrived')
        SHIPPED_TO_CUSTOMER = 'SHIPPED_TO_CUSTOMER', _('Shipped to Customer')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PAID = 'PAID', _('Paid')
        REFUNDED = 'REFUNDED', _('Refunded')
        CANCELLED = 'CANCELLED', _('Cancelled')
        

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buy4me_requests'
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_buy4me_requests',
        null=True,
        blank=True,
        help_text=_('Staff member assigned to handle this request')
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='driver_buy4me_requests',
        null=True,
        blank=True,
        help_text=_('Driver assigned to deliver this request')
    )
    city = models.ForeignKey(
        'accounts.City',
        on_delete=models.SET_NULL,
        related_name='buy4me_requests',
        null=True,
        blank=True,
        help_text=_('City for delivery, determines delivery charge and assigned driver')
    )
    city_delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text=_('Delivery charge from warehouse to customer city')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    shipping_address = models.TextField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request #{self.id} by {self.user.username}"

    def calculate_total_cost(self):
        """Calculate total cost including items, store-to-warehouse delivery charges, and city delivery charge"""
        # Calculate items total (unit_price * quantity for each item)
        items_total = Decimal('0.00')
        for item in self.items.all():
            # Add item price (quantity * unit_price)
            items_total += item.quantity * item.unit_price
            # Add store-to-warehouse delivery charge
            items_total += item.store_to_warehouse_delivery_charge
        
        # Add city delivery charge
        self.total_cost = items_total + self.city_delivery_charge
        self.save(update_fields=['total_cost'])
        return self.total_cost

    def save(self, *args, **kwargs):
        # If city is set but driver is not, try to assign a driver
        if self.city and not self.driver:
            # Get active drivers assigned to this city using apps.get_model
            DriverProfile = apps.get_model('accounts', 'DriverProfile')
            driver_profiles = DriverProfile.objects.filter(
                cities=self.city,
                is_active=True
            )
            driver_profile = driver_profiles.first()
            if driver_profile:
                self.driver = driver_profile.user
        
        # If city is set, always update the city_delivery_charge to match the city's delivery charge
        if self.city:
            self.city_delivery_charge = self.city.delivery_charge
        # If city is removed, reset delivery charge to 0
        elif self.city is None:
            self.city_delivery_charge = Decimal('0.00')
            
        super().save(*args, **kwargs)


class Buy4MeItem(SixDigitIDMixin, models.Model):
    buy4me_request = models.ForeignKey(
        Buy4MeRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product_name = models.CharField(max_length=255)
    product_url = models.URLField(max_length=1000)
    quantity = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    store_to_warehouse_delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text=_('Delivery charge from store to our warehouse')
    )
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product_name} ({self.quantity}x)"

    @property
    def total_price(self):
        """Calculate total price only for unit_price * quantity"""
        if self.quantity is not None and self.unit_price is not None:
            return self.quantity * self.unit_price
        return Decimal('0.00')
