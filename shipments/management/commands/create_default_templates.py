from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from shipments.models import ShipmentMessageTemplate


class Command(BaseCommand):
    help = 'Creates default message templates if they do not exist'

    def handle(self, *args, **options):
        template_types = ShipmentMessageTemplate.TemplateType.choices
        existing_types = set(ShipmentMessageTemplate.objects.values_list('template_type', flat=True))
        created_count = 0
        
        with transaction.atomic():
            for template_type, display_name in template_types:
                if template_type not in existing_types:
                    self._create_template(template_type)
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created '{display_name}' template")
                    )
        
        if created_count == 0:
            self.stdout.write(self.style.WARNING("All default templates already exist."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {created_count} message templates.")
            )
    
    def _create_template(self, template_type):
        """Create default template based on type"""
        if template_type == 'confirmation':
            ShipmentMessageTemplate.objects.create(
                template_type=template_type,
                subject='Your Shipment Has Been Confirmed',
                message_content="""Dear {recipient_name},

Your shipment has been confirmed and is now being processed. You can track your shipment using tracking number: {tracking_number}.

Shipment Details:
- Sender: {sender_name}
- From: {sender_country}
- Package Type: {package_type}
- Weight: {weight} kg
- Dimensions: {dimensions} cm

Estimated delivery date: {estimated_delivery}.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
            )
        elif template_type == 'notification':
            ShipmentMessageTemplate.objects.create(
                template_type=template_type,
                subject='Your Shipment Is On The Way',
                message_content="""Dear {recipient_name},

We'd like to inform you that a package from {sender_name} in {sender_country} is on its way to you. The tracking number for this shipment is: {tracking_number}.

Current Status: {status}
Current Location: {current_location}

Shipment Origin: {sender_country}
Sender Contact: {sender_email} / {sender_phone}

Our delivery team will contact you prior to delivery. Please ensure someone is available to receive the package.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
            )
        elif template_type == 'delivery':
            ShipmentMessageTemplate.objects.create(
                template_type=template_type,
                subject='Your Package Is Out For Delivery',
                message_content="""Dear {recipient_name},

Good news! Your package from {sender_name} in {sender_country} is out for delivery today. Please ensure someone is available at the delivery address to receive the package.

Tracking Number: {tracking_number}
Package Type: {package_type}
Weight: {weight} kg

If you have any special delivery instructions, please contact our customer service team immediately.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
            )
        elif template_type == 'custom':
            ShipmentMessageTemplate.objects.create(
                template_type=template_type,
                subject='Update On Your Shipment',
                message_content="""Dear {sender_name},

We have an update regarding your shipment from {sender_country}. Tracking Number: {tracking_number}
Current Status: {status}

Sender: {sender_name}
Origin: {sender_country}

Please check our website or tracking portal for more details.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
            )
        elif template_type == 'sender_notification':
            ShipmentMessageTemplate.objects.create(
                template_type=template_type,
                subject='Your Shipment Has Been Created - Payment Required',
                message_content="""Dear {sender_name},

Thank you for creating a shipment with Grade-A Express. Your shipment has been successfully registered in our system and is awaiting payment.

Shipment Details:
- Tracking Number: {tracking_number}
- Package Type: {package_type}
- Weight: {weight} kg
- Dimensions: {dimensions} cm
- Declared Value: ${declared_value}
- Total Cost: ${total_cost}

Recipient Information:
- Name: {recipient_name}
- Country: {recipient_country}
- Address: {recipient_address}
- Phone: {recipient_phone}

Payment Information:
- Payment Method: {payment_method}
- Payment Status: {payment_status}

To complete your payment and proceed with shipping, please log in to your shipping panel using the following credentials:
- Phone Number: {user_phone}
- Password: {user_password}

You can access your shipping panel at: https://www.gradeaexpress.com/login

If you have already received your login details, please use those to access the system. Once logged in, navigate to "My Shipments" and select this shipment to complete the payment process.

If you have any questions or need assistance, please contact our customer support team.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
            ) 