import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .email import send_shipment_created_email, send_status_update_email
from .models import ShipmentExtras, ShipmentRequest
from .utils import calculate_shipping_cost

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=ShipmentRequest)
def recalculate_shipping_cost(sender, instance, **kwargs):
    """
    Recalculate shipping cost when relevant fields change
    This is especially useful for admin panel changes
    """
    if not instance.pk:  # Skip for new instances (handled by serializer)
        return
        
    try:
        # Check if we're coming from the admin panel or there are field changes
        # that should trigger recalculation
        old_instance = sender.objects.get(pk=instance.pk)
        
        # Check for changes in fields that affect pricing
        fields_to_check = [
            'sender_country_id', 'recipient_country_id', 'service_type_id',
            'weight', 'length', 'width', 'height', 'city_id'
        ]
        
        # Also check if extras have changed
        old_extras = list(ShipmentExtras.objects.filter(shipment=old_instance).values('extra_id', 'quantity'))
        
        should_recalculate = False
        for field in fields_to_check:
            old_value = getattr(old_instance, field, None)
            new_value = getattr(instance, field, None)
            
            if old_value != new_value:
                should_recalculate = True
                break
        
        # Force recalculation if we're coming from admin panel 
        # (for cases where only extras are changed)
        if not should_recalculate and hasattr(instance, '_from_admin') and instance._from_admin:
            should_recalculate = True
            
        # Force recalculation if triggered by extras change
        if not should_recalculate and hasattr(instance, '_from_extras_change') and instance._from_extras_change:
            should_recalculate = True
        
        if not should_recalculate:
            return
            
        logger.info(f"Recalculating cost for shipment {instance.id} due to field changes")
        
        # Get extras from the shipment
        extras_data = []
        for shipment_extra in ShipmentExtras.objects.filter(shipment=instance):
            extras_data.append({
                'id': shipment_extra.extra.id,
                'quantity': shipment_extra.quantity
            })
        
        # Prepare dimensions
        dimensions = None
        if instance.length and instance.width and instance.height:
            dimensions = {
                'length': instance.length,
                'width': instance.width,
                'height': instance.height
            }
        
        # Calculate shipping cost
        cost_breakdown = calculate_shipping_cost(
            sender_country_id=instance.sender_country_id,
            recipient_country_id=instance.recipient_country_id,
            service_type_id=instance.service_type_id,
            weight=instance.weight,
            dimensions=dimensions,
            city_id=instance.city_id if instance.city else None,
            extras_data=extras_data
        )
        
        # Check for errors
        if cost_breakdown['errors']:
            logger.warning(f"Cost recalculation errors for shipment {instance.id}: {cost_breakdown['errors']}")
            return
            
        # Update instance fields with the new cost breakdown
        instance.weight_charge = cost_breakdown['weight_charge']
        instance.service_charge = cost_breakdown['service_price']
        instance.delivery_charge = cost_breakdown['city_delivery_charge']
        
        # Calculate extras_charges
        if 'extras_total' in cost_breakdown:
            instance.extras_charges = cost_breakdown['extras_total']
            
        # Recalculate total_cost
        instance.total_cost = instance.calculate_total_cost()
        
        logger.info(f"Updated cost for shipment {instance.id}: total={instance.total_cost}")
        
    except ObjectDoesNotExist:
        # Instance is new, no recalculation needed
        pass
    except Exception as e:
        logger.error(f"Error recalculating shipping cost: {str(e)}", exc_info=True)
        
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

@receiver(post_save, sender=ShipmentExtras)
def recalculate_on_extras_change(sender, instance, **kwargs):
    """
    Trigger recalculation when extras are changed
    """
    if instance.shipment_id:
        # Mark for recalculation and save the parent shipment
        instance.shipment._from_extras_change = True
        instance.shipment.save()

@receiver(post_delete, sender=ShipmentExtras)
def recalculate_on_extras_delete(sender, instance, **kwargs):
    """
    Trigger recalculation when extras are deleted
    """
    if instance.shipment_id:
        # Get the shipment and trigger recalculation
        try:
            shipment = ShipmentRequest.objects.get(pk=instance.shipment_id)
            shipment._from_extras_change = True
            shipment.save()
        except ShipmentRequest.DoesNotExist:
            # Shipment was already deleted, nothing to do
            pass