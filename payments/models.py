from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.utils import SixDigitIDMixin

class Invoice(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        PENDING = 'PENDING', _('Pending')
        PAID = 'PAID', _('Paid')
        OVERDUE = 'OVERDUE', _('Overdue')
        CANCELLED = 'CANCELLED', _('Cancelled')
        REFUNDED = 'REFUNDED', _('Refunded')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    # Can be linked to either a shipment or buy4me request
    shipment = models.OneToOneField(
        'shipments.ShipmentRequest',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoice'
    )
    buy4me_request = models.OneToOneField(
        'buy4me.Buy4MeRequest',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoice'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    due_date = models.DateField()
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice #{self.id} - {self.status}"

    def save(self, *args, **kwargs):
        if not self.total:
            self.total = self.subtotal + self.tax
        super().save(*args, **kwargs)

class Payment(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')

    class PaymentMethod(models.TextChoices):
        STRIPE = 'STRIPE', _('Stripe')
        PAYPAL = 'PAYPAL', _('PayPal')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        CASH = 'CASH', _('Cash')

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Payment gateway transaction ID')
    )
    payment_details = models.JSONField(
        default=dict,
        help_text=_('Additional payment details from gateway')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} - {self.status}"

class Refund(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        COMPLETED = 'COMPLETED', _('Completed')
        REJECTED = 'REJECTED', _('Rejected')

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name='refunds'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    refund_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Payment gateway refund transaction ID')
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='processed_refunds'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund #{self.id} - {self.status}"
