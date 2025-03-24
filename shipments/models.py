from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

from core.utils import SixDigitIDMixin
from shipping_rates.models import Country, Extras, ServiceType

from .utils import generate_shipment_receipt, generate_tracking_number


def shipment_receipt_path(instance, filename):
    """Generate path for shipment receipts."""
    return f'shipment_receipts/{instance.tracking_number}/{filename}'


class ShipmentStatusLocation(models.Model):
    """
    Model to define locations and descriptions for each shipment status transition.
    This allows admins to customize the locations and descriptions used in tracking updates.
    """
    class StatusType(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        PICKED_UP = 'PICKED_UP', _('Picked Up')
        IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('Out for Delivery')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    status_type = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        help_text=_('Type of status transition')
    )
    location_name = models.CharField(
        max_length=255,
        help_text=_('Location name to use for this status')
    )
    description = models.TextField(
        help_text=_('Description to use for this status update')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this status location is active')
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_('Order to display in admin actions')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'status_type']
        verbose_name = _('Shipment Status Location')
        verbose_name_plural = _('Shipment Status Locations')
        unique_together = ['status_type', 'location_name']
    
    def __str__(self):
        # Get the display value for the status type using next() and a generator expression
        status_display = next((value for key, value in self.StatusType.choices if key == self.status_type), self.status_type)
        return f"{status_display} - {self.location_name}"
    
    @classmethod
    def get_status_mapping(cls):
        """
        Returns a mapping of status types to ShipmentRequest.Status values
        """
        return {
            cls.StatusType.PENDING: ShipmentRequest.Status.PENDING,
            cls.StatusType.PROCESSING: ShipmentRequest.Status.PROCESSING,
            cls.StatusType.PICKED_UP: ShipmentRequest.Status.PROCESSING,
            cls.StatusType.IN_TRANSIT: ShipmentRequest.Status.IN_TRANSIT,
            cls.StatusType.OUT_FOR_DELIVERY: ShipmentRequest.Status.IN_TRANSIT,
            cls.StatusType.DELIVERED: ShipmentRequest.Status.DELIVERED,
            cls.StatusType.CANCELLED: ShipmentRequest.Status.CANCELLED,
        }


class ShipmentExtras(models.Model):
    """Through model for shipment extras with quantity"""
    shipment = models.ForeignKey('ShipmentRequest', on_delete=models.CASCADE)
    extra = models.ForeignKey(Extras, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = _('Shipment Extra')
        verbose_name_plural = _('Shipment Extras')
        unique_together = ['shipment', 'extra']

    def __str__(self):
        return f"{self.shipment.tracking_number} - {self.extra.name} x {self.quantity}"


class ShipmentRequest(SixDigitIDMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        IN_TRANSIT = 'IN_TRANSIT', _('In Transit')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    class PaymentMethod(models.TextChoices):
        ONLINE = 'ONLINE', _('Online Payment')
        COD = 'COD', _('Cash on Delivery')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PAID = 'PAID', _('Paid')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')

    # Field tracker
    tracker = FieldTracker()
    
    # Internal flags for signaling recalculations
    _from_admin = False
    _from_extras_change = False

    # User Information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    
    # Staff Information
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_shipments',
        null=True,
        blank=True,
        help_text=_('Staff member assigned to handle this shipment')
    )

    # Driver Information
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='driver_shipments',
        null=True,
        blank=True,
        help_text=_('Driver assigned to deliver this shipment')
    )
    
    city = models.ForeignKey(
        'accounts.City',
        on_delete=models.SET_NULL,
        related_name='shipments',
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

    # Payment Information
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,
        help_text=_('Method of payment for the shipment')
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        help_text=_('Current status of the payment')
    )
    cod_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=Decimal('0'),
        help_text=_('Additional amount for Cash on Delivery (5% of total cost)')
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date and time when payment was completed')
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Payment transaction ID from payment processor')
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
    
    extras_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text=_('Total charges from extras/additional services')
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

    def calculate_total_cost(self):
        """Calculate total cost including delivery charge and COD charge if applicable"""
        # Ensure all numeric fields have a valid value to prevent None errors
        weight_charge = self.weight_charge or Decimal('0')
        service_charge = self.service_charge or Decimal('0')
        total_additional_charges = self.total_additional_charges or Decimal('0')
        extras_charges = self.extras_charges or Decimal('0')
        delivery_charge = self.delivery_charge or Decimal('0')
        
        subtotal = (
            weight_charge + 
            service_charge +
            total_additional_charges +
            extras_charges
        )
        
        # Add 5% COD charge if payment method is COD
        if self.payment_method == self.PaymentMethod.COD:
            self.cod_amount = round(subtotal * Decimal('0.05'), 2)
            return round(subtotal + self.cod_amount + delivery_charge, 2)
        
        self.cod_amount = Decimal('0')
        return round(subtotal + delivery_charge, 2)

    def save(self, *args, **kwargs):
        is_new = not self.pk
        
        # Generate tracking number if not set
        if not self.tracking_number:
            self.tracking_number = generate_tracking_number()
        
        # Ensure all numeric fields have valid values to prevent None errors
        if self.base_rate is None:
            self.base_rate = Decimal('0')
        if self.per_kg_rate is None:
            self.per_kg_rate = Decimal('0')
        if self.weight_charge is None:
            # Only calculate weight_charge if it's not already set
            self.weight_charge = self.weight * self.per_kg_rate
        if self.service_charge is None:
            self.service_charge = Decimal('0')
        if self.total_additional_charges is None:
            self.total_additional_charges = Decimal('0')
        if self.extras_charges is None:
            self.extras_charges = Decimal('0')
        if self.delivery_charge is None:
            self.delivery_charge = Decimal('0')
        if self.cod_amount is None:
            self.cod_amount = Decimal('0')
        
        # If city is set but driver is not, try to assign a driver
        if self.city and not self.driver:
            # Get active drivers assigned to this city
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
        
        # Calculate total cost if not already set
        if self.total_cost is None or self.total_cost == Decimal('0'):
            self.total_cost = self.calculate_total_cost()
        
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
            'description': description or dict(self.Status.choices)[status]
        })
        self.save()


class SupportTicket(models.Model):
    """Model for customer support tickets"""
    
    class Status(models.TextChoices):
        OPEN = 'OPEN', _('Open')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        RESOLVED = 'RESOLVED', _('Resolved')
        CLOSED = 'CLOSED', _('Closed')
    
    class Category(models.TextChoices):
        SHIPPING = 'SHIPPING', _('Shipping Issue')
        PAYMENT = 'PAYMENT', _('Payment Issue')
        TRACKING = 'TRACKING', _('Tracking Issue')
        DELIVERY = 'DELIVERY', _('Delivery Issue')
        OTHER = 'OTHER', _('Other')
    
    # Basic Information
    ticket_number = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        help_text=_("Unique ticket identifier")
    )
    subject = models.CharField(
        max_length=255,
        help_text=_("Brief description of the issue")
    )
    message = models.TextField(
        help_text=_("Detailed description of the issue")
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        help_text=_("Category of the support ticket")
    )
    
    # Status and Assignment
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        help_text=_("Current status of the ticket")
    )
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets',
        help_text=_("User who created the ticket")
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text=_("Staff member assigned to handle this ticket")
    )
    shipment = models.ForeignKey(
        'ShipmentRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets',
        help_text=_("Related shipment if applicable")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the ticket was resolved")
    )
    
    # Comments
    comments = models.JSONField(
        default=list,
        help_text=_("List of comments on this ticket")
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Ticket #{self.ticket_number} - {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Generate unique ticket number
            prefix = 'TKT'
            random_digits = get_random_string(9, '0123456789')
            self.ticket_number = f"{prefix}{random_digits}"
        
        # Update resolved_at when status changes to RESOLVED
        if self.status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def add_comment(self, user, comment):
        """Add a comment to the ticket"""
        self.comments.append({
            'user': str(user),
            'comment': comment,
            'timestamp': timezone.now().isoformat(),
            'is_staff': getattr(user, 'is_staff', False)
        })
        self.save()


class ShipmentMessageTemplate(models.Model):
    """
    Model for storing customizable message templates for shipment communications.
    This allows staff to update message formats without changing code.
    """
    class TemplateType(models.TextChoices):
        CONFIRMATION = 'confirmation', _('Shipment Confirmation')
        NOTIFICATION = 'notification', _('Shipment Notification')
        DELIVERY = 'delivery', _('Delivery Notification')
        SENDER_NOTIFICATION = 'sender_notification', _('Sender Notification')
        CUSTOM = 'custom', _('Custom Message')
    
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        unique=True,
        help_text=_('Type of message template')
    )
    subject = models.CharField(
        max_length=200,
        help_text=_('Subject line for email communications')
    )
    message_content = models.TextField(
        help_text=_(
            'Message template with placeholders. Available placeholders: '
            '{recipient_name}, {sender_name}, {sender_country}, {tracking_number}, '
            '{package_type}, {weight}, {dimensions}, {status}, {current_location}, '
            '{estimated_delivery}, {description}, {sender_email}, {sender_phone}'
        )
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this template is currently active')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Shipment Message Template')
        verbose_name_plural = _('Shipment Message Templates')
        ordering = ['template_type']
    
    def __str__(self):
        return f"{self.get_template_type_display()}"
    
    def preview_with_sample_data(self):
        """Generate a sample preview with placeholder data"""
        from datetime import datetime, timedelta

        # Sample data for preview
        sample_data = {
            'recipient_name': 'John Doe',
            'sender_name': 'ABC Company',
            'sender_country': 'United States',
            'tracking_number': 'TRK123456789',
            'package_type': 'Package',
            'weight': '2.5',
            'dimensions': '30 × 20 × 15',
            'status': 'In Transit',
            'current_location': 'Distribution Center, New York',
            'estimated_delivery': (datetime.now() + timedelta(days=3)).strftime('%d %B %Y'),
            'description': 'Electronics and accessories',
            'sender_email': 'shipper@example.com',
            'sender_phone': '+1234567890',
        }
        
        # Replace placeholders in the message content
        preview = self.message_content
        for key, value in sample_data.items():
            placeholder = '{' + key + '}'
            preview = preview.replace(placeholder, str(value))
            
        return preview


