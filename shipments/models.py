from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.utils import SixDigitIDMixin
from shipping_rates.models import ServiceType, Country
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.core.files.base import ContentFile
from model_utils import FieldTracker
from .utils import generate_shipment_receipt


def shipment_receipt_path(instance, filename):
    """Generate path for shipment receipts."""
    return f'shipment_receipts/{instance.tracking_number}/{filename}'

class ShipmentRequest(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Field tracker
    tracker = FieldTracker()

    # User Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipments'
    )

    # Receipt PDF
    receipt = models.FileField(
        upload_to=shipment_receipt_path,
        null=True,
        blank=True,
        help_text=_('PDF receipt for the shipment')
    )

    # Sender Information
    sender_name = models.CharField(max_length=255)
    sender_email = models.EmailField(max_length=254)
    sender_phone = models.CharField(max_length=20)
    sender_address = models.TextField()
    sender_country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='shipments_as_sender',
        limit_choices_to={'country_type': Country.CountryType.DEPARTURE}
    )

    # Recipient Information
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField(max_length=254)
    recipient_phone = models.CharField(max_length=20)
    recipient_address = models.TextField()
    recipient_country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='shipments_as_recipient',
        limit_choices_to={'country_type': Country.CountryType.DESTINATION}
    )

    # Package Information
    package_type = models.CharField(max_length=50)  # e.g., Document, Parcel, Box
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
  
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    description = models.TextField(help_text=_('Package contents description'))
    declared_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Declared value for customs')
    )

    # Service Options
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    insurance_required = models.BooleanField(
        default=False,
        help_text=_('Whether insurance is required for the shipment')
    )
    signature_required = models.BooleanField(
        default=False,
        help_text=_('Whether signature is required upon delivery')
    )

    # Tracking Information
    tracking_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Unique tracking number for the shipment")
    )
    current_location = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Current location of the shipment")
    )
    tracking_history = models.JSONField(
        default=list,
        help_text=_("List of tracking updates with timestamp and location")
    )
    estimated_delivery = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Estimated delivery date and time")
    )

    # Status Information
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Cost Information
    base_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    per_kg_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    weight_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    service_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    total_additional_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    # Additional Information
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Shipment #{self.tracking_number or self.id} - {self.status}"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        
        if not self.tracking_number:
            # Generate unique tracking number
            prefix = 'TRK'
            random_digits = get_random_string(9, '0123456789')
            self.tracking_number = f"{prefix}{random_digits}"
            
            # Add initial tracking entry
            self.tracking_history.append({
                'status': self.Status.PENDING,
                'location': 'Order Received',
                'timestamp': timezone.now().isoformat(),
                'description': 'Shipment request created'
            })
        
        # Calculate total cost
        self.weight_charge = self.weight * self.per_kg_rate
        self.total_cost = (
            self.base_rate + 
            self.weight_charge + 
            self.service_charge +
            self.total_additional_charges
        )
        
        # Save the model first
        super().save(*args, **kwargs)
        
        # Generate receipt if it's a new shipment or status has changed
        if is_new or self.tracker.has_changed('status'):
            # Generate PDF receipt
            pdf_content = generate_shipment_receipt(self)
            
            # Save the PDF
            filename = f'shipment_receipt_{self.tracking_number}.pdf'
            if self.receipt:
                self.receipt.delete(save=False)  # Delete old receipt if exists
            self.receipt.save(filename, ContentFile(pdf_content), save=True)

    def update_tracking(self, status, location, description=None):
        """Update shipment tracking information"""
        self.status = status
        self.current_location = location
        
        self.tracking_history.append({
            'status': status,
            'location': location,
            'timestamp': timezone.now().isoformat(),
            'description': description or self.get_status_display()
        })
        self.save()


