import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .email import send_shipment_created_email, send_status_update_email
from .models import ShipmentExtras, ShipmentPackage, ShipmentRequest
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
        
        # Ensure per_kg_rate is correctly set
        if 'per_kg_rate' in cost_breakdown:
            instance.per_kg_rate = cost_breakdown['per_kg_rate']
        
        # Update total_additional_charges by summing the amounts
        total_additional = Decimal('0.00')
        for charge in cost_breakdown['additional_charges']:
            total_additional += Decimal(str(charge['amount']))
        instance.total_additional_charges = total_additional
        
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
        # Calculate COD amount using dynamic rate from DynamicRate model
        try:
            # Import here to avoid circular imports
            from shipping_rates.models import DynamicRate

            # Try to get COD fee from DynamicRate
            cod_rate = DynamicRate.objects.filter(
                rate_type=DynamicRate.RateType.COD_FEE,
                charge_type=DynamicRate.ChargeType.PERCENTAGE,
                is_active=True
            ).first()
            
            if cod_rate:
                # Use the dynamic rate value
                cod_percentage = cod_rate.value / 100  # Convert percentage to decimal
            else:
                # Fallback to default 5% if no dynamic rate is found
                cod_percentage = Decimal('0.05')
                
            cod_amount = round(instance.total_cost * cod_percentage, 2)
        except (ImportError, Exception):
            # Fallback to default 5% if any error occurs
            cod_amount = round(instance.total_cost * Decimal("0.05"), 2)
        
        # Only update if the COD amount has changed
        if instance.cod_amount != cod_amount:
            instance.cod_amount = cod_amount
            # Add COD amount to total cost
            instance.total_cost = instance.total_cost + cod_amount
            # Save both cod_amount and total_cost to avoid re-triggering the signal
            ShipmentRequest.objects.filter(id=instance.id).update(
                cod_amount=cod_amount,
                total_cost=instance.total_cost
            )
    elif instance.payment_method == ShipmentRequest.PaymentMethod.ONLINE:
        # Remove COD amount from total cost for online payments
        if instance.cod_amount != Decimal("0"):
            # Subtract the current COD amount from total cost
            instance.total_cost = instance.total_cost - instance.cod_amount
            instance.cod_amount = Decimal("0")
            # Save both cod_amount and total_cost to prevent recursion
            ShipmentRequest.objects.filter(id=instance.id).update(
                cod_amount=Decimal("0"),
                total_cost=instance.total_cost
            )

@receiver(post_save, sender=ShipmentExtras)
def recalculate_on_extras_change(sender, instance, **kwargs):
    """
    Trigger recalculation when extras are changed
    """
    if instance.shipment_id:
        # Directly update the shipment without using flags
        try:
            # Set a flag on the instance to avoid recursion in pre_save signal
            instance.shipment._from_extras_change = True
            
            # Manually call the recalculate function
            from .utils import calculate_shipping_cost

            # Get shipment with all related fields
            shipment = ShipmentRequest.objects.get(pk=instance.shipment.pk)
            
            # Get all extras from the shipment
            extras_data = []
            for shipment_extra in ShipmentExtras.objects.filter(shipment=shipment):
                extras_data.append({
                    'id': shipment_extra.extra.id,
                    'quantity': shipment_extra.quantity
                })
            
            # Prepare dimensions
            dimensions = None
            if shipment.length and shipment.width and shipment.height:
                dimensions = {
                    'length': shipment.length,
                    'width': shipment.width,
                    'height': shipment.height
                }
            
            # Calculate shipping cost
            cost_breakdown = calculate_shipping_cost(
                sender_country_id=shipment.sender_country.id,
                recipient_country_id=shipment.recipient_country.id,
                service_type_id=shipment.service_type.id,
                weight=shipment.weight,
                dimensions=dimensions,
                city_id=shipment.city.id if shipment.city else None,
                extras_data=extras_data
            )
            
            # Check for errors
            if cost_breakdown['errors']:
                logger.warning(f"Cost recalculation errors for shipment {shipment.id}: {cost_breakdown['errors']}")
                return
                
            # Update shipment fields with the new cost breakdown
            shipment.weight_charge = cost_breakdown['weight_charge']
            shipment.service_charge = cost_breakdown['service_price']
            shipment.delivery_charge = cost_breakdown['city_delivery_charge']
            
            # Ensure per_kg_rate is correctly set
            if 'per_kg_rate' in cost_breakdown:
                shipment.per_kg_rate = cost_breakdown['per_kg_rate']
            
            # Explicitly calculate and set total_additional_charges from the cost_breakdown
            total_additional = Decimal('0.00')
            for charge in cost_breakdown['additional_charges']:
                total_additional += Decimal(str(charge['amount']))
            shipment.total_additional_charges = total_additional
            
            # Calculate extras_charges
            if 'extras_total' in cost_breakdown:
                shipment.extras_charges = cost_breakdown['extras_total']
                
            # Recalculate total_cost
            shipment.total_cost = shipment.calculate_total_cost()
            
            # Save the shipment with updated fields only to prevent recursion
            ShipmentRequest.objects.filter(pk=shipment.pk).update(
                weight_charge=shipment.weight_charge,
                service_charge=shipment.service_charge,
                delivery_charge=shipment.delivery_charge,
                per_kg_rate=shipment.per_kg_rate,
                total_additional_charges=shipment.total_additional_charges,
                extras_charges=shipment.extras_charges,
                total_cost=shipment.total_cost
            )
            
            logger.info(f"Updated cost for shipment {shipment.id}: total={shipment.total_cost}")
        except Exception as e:
            logger.error(f"Error recalculating shipping cost: {str(e)}", exc_info=True)

@receiver(post_delete, sender=ShipmentExtras)
def recalculate_on_extras_delete(sender, instance, **kwargs):
    """
    Trigger recalculation when extras are deleted
    """
    if instance.shipment_id:
        # Get the shipment and trigger direct recalculation
        try:
            # Get shipment with all related fields
            shipment = ShipmentRequest.objects.get(pk=instance.shipment_id)
            
            # Set a flag on the instance to avoid recursion in pre_save signal
            shipment._from_extras_change = True
            
            # Call the same recalculation logic used in post_save handler
            recalculate_on_extras_change(sender, instance, **kwargs)
        except ShipmentRequest.DoesNotExist:
            # Shipment was already deleted, nothing to do
            pass

@receiver(post_save, sender=ShipmentRequest)
def create_shipment_packages(sender, instance, created, **kwargs):
    """Create shipment packages when a shipment is created"""
    if created:
        logger.info(f"Creating {instance.no_of_packages} package(s) for shipment {instance.tracking_number}")
        try:
            # Create packages based on no_of_packages value
            for i in range(1, instance.no_of_packages + 1):
                ShipmentPackage.objects.create(
                    shipment=instance,
                    package_type=instance.package_type,
                    number=i,
                    status=ShipmentPackage.Status.PENDING
                )
            logger.info(f"Successfully created {instance.no_of_packages} package(s) for shipment {instance.tracking_number}")
        except Exception as e:
            logger.error(f"Error creating packages for shipment {instance.tracking_number}: {str(e)}", exc_info=True)