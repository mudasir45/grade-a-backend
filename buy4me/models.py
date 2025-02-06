from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

class Buy4MeRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SUBMITTED = 'SUBMITTED', _('Submitted')
        ORDER_PLACED = 'ORDER_PLACED', _('Order Placed')
        IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
        WAREHOUSE_ARRIVED = 'WAREHOUSE_ARRIVED', _('Warehouse Arrived')
        SHIPPED_TO_CUSTOMER = 'SHIPPED_TO_CUSTOMER', _('Shipped to Customer')
        COMPLETED = 'COMPLETED', _('Completed')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buy4me_requests'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
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

class Buy4MeItem(models.Model):
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
        return self.quantity * self.unit_price
