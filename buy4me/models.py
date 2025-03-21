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
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text=_('Fixed delivery charge based on city')
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
        """Calculate total cost including items and service fee"""
        items_total = self.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        # Add service fee logic here if needed
        self.total_cost = items_total
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
        
        # If city is set but delivery_charge is not, set it from the city
        if self.city and self.delivery_charge == Decimal('0.00'):
            self.delivery_charge = self.city.delivery_charge
            
        super().save(*args, **kwargs)

class Buy4MeItem(SixDigitIDMixin, models.Model):
    buy4me_request = models.ForeignKey(
        Buy4MeRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product_name = models.CharField(max_length=255)
    product_url = models.URLField()
    quantity = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
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
        """Calculate total price only if both quantity and unit_price exist"""
        if self.quantity is not None and self.unit_price is not None:
            return self.quantity * self.unit_price
        return 0  # or return None if you prefer
