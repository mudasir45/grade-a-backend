from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
import logging
from .models import ShipmentRequest
from .email import send_shipment_created_email, send_status_update_email

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