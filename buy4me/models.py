from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.utils import SixDigitIDMixin
from shipping_rates.models import DynamicRate


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
    service_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    service_fee_percentage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(0)]
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
        """Calculate total cost including items and store-to-warehouse delivery charges"""
        # Calculate items total (unit_price * quantity for each item)
        items_total = Decimal('0.00')
        for item in self.items.all():
            # Add item price (quantity * unit_price)
            items_total += item.quantity * item.unit_price
            # Add store-to-warehouse delivery charge
            items_total += item.store_to_warehouse_delivery_charge
        
        service_fee = DynamicRate.objects.filter(
            rate_type=DynamicRate.RateType.BUY4ME_FEE,
            charge_type=DynamicRate.ChargeType.PERCENTAGE,
            is_active=True
        ).first()
        
        service_fee_percentage = Decimal('0.10')
        if service_fee:
            service_fee_percentage = service_fee.value / 100
            self.service_fee_percentage = service_fee.value
        else:
            service_fee_percentage = Decimal('0.10')
            self.service_fee_percentage = Decimal('10.00')
            
            
        
        service_fee_amount = items_total * service_fee_percentage
        items_total += service_fee_amount
        
        
        
        # Set total cost to items total
        self.total_cost = items_total
        self.service_fee = service_fee_amount
        
        self.save(update_fields=['total_cost', 'service_fee', 'service_fee_percentage'])
        return self.total_cost

    def save(self, *args, **kwargs):
        # Save the model
        super().save(*args, **kwargs)
        
        # If we're saving with update_fields and it contains only total_cost and/or service_fee,
        # don't recalculate to avoid infinite recursion
        if 'update_fields' in kwargs and set(kwargs['update_fields']).issubset({'total_cost', 'service_fee', 'service_fee_percentage'}):
            return
            
        # Otherwise recalculate total cost (for new objects or when other fields change)
        self.calculate_total_cost()


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

    def save(self, *args, **kwargs):
        # First check if this is an existing instance being updated
        if self.pk:
            # Get the old instance from the database
            old_instance = Buy4MeItem.objects.get(pk=self.pk)
            # Check if any cost-related fields have changed
            price_changed = (
                old_instance.quantity != self.quantity or
                old_instance.unit_price != self.unit_price or
                old_instance.store_to_warehouse_delivery_charge != self.store_to_warehouse_delivery_charge
            )
        else:
            # New instance, price has effectively changed
            price_changed = True
            
        # Save the item
        super().save(*args, **kwargs)
        
        # If cost-related fields changed, recalculate the total cost of the parent request
        if price_changed and self.buy4me_request:
            self.buy4me_request.calculate_total_cost()
