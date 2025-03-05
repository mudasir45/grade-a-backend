import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver

from .email import send_shipment_created_email, send_status_update_email
from .models import ShipmentRequest

logger = logging.getLogger(__name__)

@receiver(post_save, sender=ShipmentRequest)
def handle_shipment_notifications(sender, instance, created, **kwargs):
    """
    Handle email notifications for shipment creation and status updates
    """
    try:
        if created:
            logger.info(f"Sending creation notification for shipment {instance.tracking_number}")
            send_shipment_created_email(instance)
            logger.info(f"Creation notification sent successfully for shipment {instance.tracking_number}")
        else:
            # Check if status has changed
            if instance.tracker.has_changed('status'):
                old_status = instance.tracker.previous('status')
                new_status = instance.status
                logger.info(
                    f"Status changed for shipment {instance.tracking_number} "
                    f"from {old_status} to {new_status}"
                )
                send_status_update_email(instance)
                logger.info(f"Status update notification sent for shipment {instance.tracking_number}")

    except Exception as e:
        logger.error(
            f"Error sending notification for shipment {instance.tracking_number}: {str(e)}",
            exc_info=True
        )
        if settings.DEBUG:
            raise  # Re-raise the exception in debug mode 
        


@receiver(post_save, sender=ShipmentRequest)
def handle_shipment_payment_method(sender, instance, created, **kwargs):
    """
    Handle payment method and extra charges for shipment
    """
    if instance.payment_method == ShipmentRequest.PaymentMethod.COD:
        instance.cod_amount = instance.total_cost * Decimal("0.05")

        # Save only the `cod_amount` field to avoid re-triggering the signal
        ShipmentRequest.objects.filter(id=instance.id).update(cod_amount=instance.cod_amount)

    elif instance.payment_method == ShipmentRequest.PaymentMethod.ONLINE:
        instance.cod_amount = Decimal("0")

        # Save only `cod_amount` to prevent recursion
        ShipmentRequest.objects.filter(id=instance.id).update(cod_amount=instance.cod_amount)