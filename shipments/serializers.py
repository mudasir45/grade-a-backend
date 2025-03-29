from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import City
from accounts.serializers import CitySerializer, UserSerializer
from shipping_rates.models import (Country, DimensionalFactor, Extras,
                                   ServiceType, ShippingZone, WeightBasedRate)

from .models import (ShipmentExtras, ShipmentMessageTemplate, ShipmentRequest,
                     ShipmentStatusLocation, SupportTicket)


class ShipmentRequestSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    user_id = serializers.CharField(source='user.id', read_only=True)
    staff = serializers.StringRelatedField(read_only=True)
    driver = serializers.StringRelatedField(read_only=True)
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), required=False, allow_null=True)
    cod_amount = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    per_kg_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_additional_charges = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=ShipmentRequest.PaymentMethod.choices)
    payment_status = serializers.ChoiceField(choices=ShipmentRequest.PaymentStatus.choices)
    extras = serializers.SerializerMethodField()
    additional_charges = serializers.ListField(required=False, write_only=True)

    class Meta:
        model = ShipmentRequest
        fields = '__all__'
        read_only_fields = [
            'user', 'staff', 'driver', 'tracking_number', 'status',
            'current_location', 'estimated_delivery',
            'tracking_history', 'weight_charge', 'total_cost', 'created_at', 'updated_at',
            'cod_amount', 'payment_status', 'payment_date',
            'transaction_id', 'delivery_charge'
        ]

    def get_extras(self, obj):
        shipment_extras = ShipmentExtras.objects.filter(shipment=obj)
        return [
            {
                'id': item.extra.id,
                'name': item.extra.name,
                'quantity': item.quantity,
                'charge_type': item.extra.charge_type,
                'value': item.extra.value
            }
            for item in shipment_extras
        ]

    def to_internal_value(self, data):
        """
        Custom handling of raw data from requests
        """
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Set defaults for required decimal fields to prevent None errors
        decimal_fields = ['weight_charge', 'total_additional_charges', 
                          'extras_charges', 'total_cost', 'per_kg_rate']
        for field in decimal_fields:
            if field not in data_copy or not data_copy[field]:
                data_copy[field] = '0.00'
            else:
                # Ensure decimal fields have max 2 decimal places
                try:
                    value = Decimal(str(data_copy[field]))
                    data_copy[field] = str(round(value, 2))
                except (TypeError, ValueError):
                    data_copy[field] = '0.00'
        
        return super().to_internal_value(data_copy)

    def update(self, instance, validated_data):
        """Update the shipment"""
        # Extract extras data
        additional_charges = validated_data.pop('additional_charges', [])
        
        # Update ShipmentExtras if extras data is provided
        if additional_charges:
            # Clear existing extras
            ShipmentExtras.objects.filter(shipment=instance).delete()
            
            # Calculate extras charges from the extras data
            extras_charges = Decimal('0.00')
            from shipping_rates.models import Extras
            
            for extra_data in additional_charges:
                if not isinstance(extra_data, dict):
                    continue
                    
                try:
                    # Get or retrieve the Extras object
                    extra_id = extra_data.get('id')
                    if not extra_id:
                        continue
                        
                    extra_obj = Extras.objects.get(id=extra_id)
                    
                    # Create the ShipmentExtras object
                    quantity = int(extra_data.get('quantity', 1))
                    ShipmentExtras.objects.create(
                        shipment=instance,
                        extra=extra_obj,
                        quantity=quantity
                    )
                    
                    # Add to extras_charges
                    if 'amount' in extra_data:
                        extras_charges += Decimal(str(extra_data.get('amount', 0)))
                    else:
                        value = Decimal(str(extra_data.get('value', 0)))
                        extras_charges += value * quantity
                except (Extras.DoesNotExist, Exception) as e:
                    print(f"Error creating shipment extra: {e}")
                    continue
            
            # Update extras_charges in validated_data
            validated_data['extras_charges'] = round(extras_charges, 2)
        
        # Update the instance with the validated data
        return super().update(instance, validated_data)


class ShipmentExtrasSerializer(serializers.ModelSerializer):
    """Serializer for ShipmentExtras model"""
    extra_id = serializers.PrimaryKeyRelatedField(
        source='extra',
        queryset=Extras.objects.all()
    )
    quantity = serializers.IntegerField(min_value=1)
    
    class Meta:
        model = ShipmentExtras
        fields = ['extra_id', 'quantity']


class ShipmentCreateSerializer(serializers.ModelSerializer):
    payment_method = serializers.ChoiceField(
        choices=ShipmentRequest.PaymentMethod.choices,
        default=ShipmentRequest.PaymentMethod.ONLINE
    )
    
    # Allow blank email fields
    sender_email = serializers.EmailField(max_length=254, allow_blank=True)
    recipient_email = serializers.EmailField(max_length=254, allow_blank=True)
    
    # Accept extras data directly
    additional_charges = serializers.ListField(required=False)
    extras_charges = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    weight_charge = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_additional_charges = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    per_kg_rate = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    cost_breakdown = serializers.JSONField(required=False)

    class Meta:
        model = ShipmentRequest
        fields = [
            'sender_name', 'sender_email', 'sender_phone',
            'sender_address', 'sender_country',
            'recipient_name', 'recipient_email', 'staff', 'recipient_phone',
            'recipient_address', 'recipient_country', 'city', 
            'additional_charges', 'extras_charges',
            'package_type', 'weight', 'length', 'width', 'height',
            'description', 'declared_value', 'weight_charge',
            'total_additional_charges', 'total_cost',
            'service_type', 'insurance_required', 'signature_required',
            'payment_method', 'notes', 'cost_breakdown', 'per_kg_rate'
        ]
        read_only_fields = [
            'tracking_number', 'status', 'current_location',
            'estimated_delivery', 'tracking_history',
            'cod_amount', 'payment_status', 'payment_date',
            'transaction_id'
        ]

    def to_internal_value(self, data):
        """
        Custom handling of raw data from requests,
        especially for extras parsing.
        """
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Get cost breakdown data if available
        cost_breakdown = data_copy.get('cost_breakdown', {})
        
        # Extract values from cost_breakdown
        if cost_breakdown:
            if 'weight_charge' in cost_breakdown and 'weight_charge' not in data_copy:
                data_copy['weight_charge'] = cost_breakdown['weight_charge']
                
            if 'city_delivery_charge' in cost_breakdown and 'delivery_charge' not in data_copy:
                data_copy['delivery_charge'] = cost_breakdown['city_delivery_charge']
                
            if 'total_cost' in cost_breakdown and 'total_cost' not in data_copy:
                data_copy['total_cost'] = cost_breakdown['total_cost']
        
        # Set defaults for required decimal fields to prevent None errors
        decimal_fields = ['weight_charge', 'total_additional_charges', 
                          'extras_charges', 'total_cost', 'per_kg_rate']
        for field in decimal_fields:
            if field not in data_copy or not data_copy[field]:
                data_copy[field] = '0.00'
            else:
                # Ensure decimal fields have max 2 decimal places
                try:
                    value = Decimal(str(data_copy[field]))
                    data_copy[field] = str(round(value, 2))
                except (TypeError, ValueError):
                    data_copy[field] = '0.00'
        
        return super().to_internal_value(data_copy)

    def create(self, validated_data):
        # Extract extras data
        additional_charges = validated_data.pop('additional_charges', [])
        cost_breakdown = validated_data.pop('cost_breakdown', None)
        
        # Process extras if present in cost_breakdown
        extras_data = []
        if cost_breakdown and 'extras' in cost_breakdown:
            extras_data = cost_breakdown.get('extras', [])
        elif 'additional_charges' in validated_data:
            extras_data = additional_charges
            
        # Calculate extras charges from the extras data
        extras_charges = Decimal('0.00')
        for extra_data in extras_data:
            quantity = int(extra_data.get('quantity', 1))
            value = Decimal(str(extra_data.get('value', 0)))
            extras_charges += value * quantity
        
        # Ensure all required fields have values with proper decimal places
        if 'extras_charges' not in validated_data or not validated_data['extras_charges']:
            validated_data['extras_charges'] = round(extras_charges, 2)
            
        # Ensure all decimal fields are rounded to 2 decimal places
        decimal_fields = ['weight_charge', 'total_additional_charges', 
                          'total_cost', 'per_kg_rate']
        for field in decimal_fields:
            if field in validated_data:
                if validated_data[field] is None:
                    validated_data[field] = Decimal('0.00')
                else:
                    # Convert to Decimal if not already and round to 2 decimal places
                    value = validated_data[field]
                    if not isinstance(value, Decimal):
                        value = Decimal(str(value))
                    validated_data[field] = round(value, 2)
            else:
                validated_data[field] = Decimal('0.00')
        
        # Create the shipment
        shipment = super().create(validated_data)
        
        # Create ShipmentExtras objects
        from shipping_rates.models import Extras
        for extra_data in extras_data:
            try:
                # Get or retrieve the Extras object
                extra_id = extra_data.get('id')
                extra_obj = Extras.objects.get(id=extra_id)
                
                # Create the ShipmentExtras object
                ShipmentExtras.objects.create(
                    shipment=shipment,
                    extra=extra_obj,
                    quantity=int(extra_data.get('quantity', 1))
                )
            except (Extras.DoesNotExist, Exception) as e:
                print(f"Error creating shipment extra: {e}")
                continue
        
        return shipment


class ShipmentStatusLocationSerializer(serializers.ModelSerializer):
    """Serializer for ShipmentStatusLocation model"""
    status_type_display = serializers.CharField(source='get_status_type_display', read_only=True)
    
    class Meta:
        model = ShipmentStatusLocation
        fields = [
            'id', 'status_type', 'status_type_display', 
            'location_name', 'description', 'display_order'
        ]
        read_only_fields = ['id', 'status_type_display']


class StatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating shipment status"""
    status_location_id = serializers.IntegerField(
        required=True,
        help_text="ID of the status location to use for the update"
    )
    custom_description = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text="Optional custom description to override the default"
    )
    
    def validate_status_location_id(self, value):
        """Validate that the status location exists and is active"""
        try:
            status_location = ShipmentStatusLocation.objects.get(id=value, is_active=True)
            # Store the status location for later use
            self.context['status_location'] = status_location
            return value
        except ShipmentStatusLocation.DoesNotExist:
            raise serializers.ValidationError(
                "Status location not found or is inactive"
            )
    
    def update(self, instance, validated_data):
        """Update the shipment status"""
        status_location = self.context['status_location']
        custom_description = validated_data.get('custom_description')
        
        # Get the corresponding ShipmentRequest.Status
        status_mapping = ShipmentStatusLocation.get_status_mapping()
        shipment_status = status_mapping.get(status_location.status_type)
        
        # Use custom description if provided, otherwise use the default
        description = custom_description if custom_description else status_location.description
        
        # Update the tracking information
        instance.update_tracking(
            shipment_status,
            status_location.location_name,
            description
        )
        
        return instance 


class SupportTicketSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), required=False)
    shipment = serializers.PrimaryKeyRelatedField(queryset=ShipmentRequest.objects.all(), required=False)

    class Meta:
        model = SupportTicket
        fields = ['ticket_number', 'admin_reply', 'subject', 'message', 'category', 'status', 'user', 'assigned_to', 'shipment', 'created_at', 'updated_at', 'resolved_at', 'comments']
        read_only_fields = ['ticket_number', 'created_at', 'updated_at', 'resolved_at']

    def create(self, validated_data):
        # Handle ticket creation logic
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Handle ticket update logic
        return super().update(instance, validated_data)


class ShipmentMessageSerializer(serializers.Serializer):
    """Serializer for generating professional messages for shipments"""
    message_type = serializers.ChoiceField(
        choices=[
            ('confirmation', 'Shipment Confirmation'),
            ('notification', 'Shipment Notification'),
            ('delivery', 'Delivery Notification'),
            ('sender_notification', 'Sender Notification'),
            ('custom', 'Custom Message')
        ],
        default='confirmation',
        help_text="Type of message to generate"
    )
    include_tracking = serializers.BooleanField(
        default=True,
        help_text="Whether to include tracking information in the message"
    )
    include_sender_details = serializers.BooleanField(
        default=True,
        help_text="Whether to include sender details in the message"
    )
    include_credentials = serializers.BooleanField(
        default=False,
        help_text="Whether to include user credentials in the message (only for sender notifications)"
    )
    user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="User ID to fetch credentials from (phone and password will be retrieved automatically)"
    )
    additional_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes to include in the message"
    )
    
    def generate_message(self, shipment):
        """Generate a professional message based on shipment details and options"""
        # Access validated_data with proper checks
        if not hasattr(self, 'validated_data'):
            raise serializers.ValidationError("Serializer has not been validated yet")
            
        message_type = self.validated_data.get('message_type', 'confirmation')
        include_tracking = self.validated_data.get('include_tracking', True)
        include_sender = self.validated_data.get('include_sender_details', True)
        include_credentials = self.validated_data.get('include_credentials', False)
        user_id = self.validated_data.get('user_id', '')
        additional_notes = self.validated_data.get('additional_notes', '')
        
        # Fetch user credentials if user_id is provided
        user_phone = ''
        user_password = ''
        if include_credentials and user_id:
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                # Get phone number - check common field names
                user_phone = getattr(user, 'phone_number', '') or getattr(user, 'phone', '') or user.username
                
                # For password, use the decryption method from the User model
                if hasattr(user, 'get_plain_password'):
                    user_password = user.get_plain_password()
                # Fallbacks in case the model doesn't have the method
                elif hasattr(user, 'temp_password'):
                    user_password = user.temp_password
                elif hasattr(user, 'plain_password'):
                    # Try direct access, but this will return encrypted value
                    user_password = user.plain_password
                # If your User model stores initial password in a retrievable field, use that
                elif hasattr(user, 'initial_password'):
                    user_password = user.initial_password
                else:
                    # If we can't find a retrievable password, use this fallback
                    # This is ONLY for existing users with no saved plain password
                    from accounts.models import User as AccountUser
                    if isinstance(user, AccountUser) and hasattr(AccountUser, 'DEFAULT_PASSWORD'):
                        user_password = AccountUser.DEFAULT_PASSWORD
                    else:
                        user_password = "123456"  # Default fallback password as requested
            except User.DoesNotExist:
                pass  # If user not found, leave credentials empty
        
        # Get the template from the database
        try:
            template = ShipmentMessageTemplate.objects.get(
                template_type=message_type,
                is_active=True
            )
        except ShipmentMessageTemplate.DoesNotExist:
            # Fallback to default templates if none in the database
            return self._generate_default_message(
                shipment, message_type, include_tracking, include_sender, 
                include_credentials, user_phone, user_password, additional_notes
            )
        
        # Prepare data dictionary with all available placeholders
        sender_country = shipment.sender_country.name if shipment.sender_country else 'Unknown'
        recipient_country = shipment.recipient_country.name if hasattr(shipment, 'recipient_country') and shipment.recipient_country else 'Unknown'
        recipient_name = shipment.recipient_name.split()[0] if shipment.recipient_name else "Valued Customer"
        
        # Get status display value safely
        status_display = 'Unknown'
        if hasattr(shipment, 'get_status_display'):
            status_display = shipment.get_status_display()
        elif hasattr(shipment, 'status'):
            # Try to get from ShipmentRequest.Status choices if available
            from .models import ShipmentRequest
            status_display = dict(ShipmentRequest.Status.choices).get(shipment.status, shipment.status)
        
        # Get payment method and status display values safely
        payment_method_display = 'Online Payment'
        if hasattr(shipment, 'get_payment_method_display'):
            payment_method_display = shipment.get_payment_method_display()
        
        payment_status_display = 'Pending'
        if hasattr(shipment, 'get_payment_status_display'):
            payment_status_display = shipment.get_payment_status_display()
        
        # Format dimensions
        dimensions = f"{shipment.length} × {shipment.width} × {shipment.height}" if all([
            hasattr(shipment, attr) for attr in ['length', 'width', 'height']
        ]) else "N/A"
        
        # Format estimated delivery
        estimated_delivery = "To be determined"
        if hasattr(shipment, 'estimated_delivery') and shipment.estimated_delivery:
            estimated_delivery = shipment.estimated_delivery.strftime('%d %B %Y')
        
        # Create data dictionary with all available placeholders
        data = {
            'recipient_name': getattr(shipment, 'recipient_name', 'Valued Customer'),
            'recipient_email': getattr(shipment, 'recipient_email', ''),
            'recipient_phone': getattr(shipment, 'recipient_phone', ''),
            'recipient_address': getattr(shipment, 'recipient_address', ''),
            'recipient_country': recipient_country,
            'sender_name': getattr(shipment, 'sender_name', ''),
            'sender_email': getattr(shipment, 'sender_email', ''),
            'sender_phone': getattr(shipment, 'sender_phone', ''),
            'sender_address': getattr(shipment, 'sender_address', ''),
            'sender_country': sender_country,
            'tracking_number': getattr(shipment, 'tracking_number', ''),
            'package_type': getattr(shipment, 'package_type', 'Package'),
            'weight': f"{getattr(shipment, 'weight', 'N/A')}",
            'dimensions': dimensions,
            'declared_value': f"{getattr(shipment, 'declared_value', '0.00')}",
            'total_cost': f"{getattr(shipment, 'total_cost', '0.00')}",
            'status': status_display,
            'payment_method': payment_method_display,
            'payment_status': payment_status_display,
            'current_location': getattr(shipment, 'current_location', 'In processing'),
            'estimated_delivery': estimated_delivery,
            'description': getattr(shipment, 'description', ''),
        }
        
        # Add user credentials if requested
        if include_credentials and message_type == 'sender_notification':
            # If user_id wasn't provided, try to get credentials from shipment.user
            if not user_phone and hasattr(shipment, 'user') and shipment.user:
                user_phone = getattr(shipment.user, 'phone_number', '') or getattr(shipment.user, 'phone', '') or getattr(shipment.user, 'username', '')
            
            data['user_phone'] = user_phone
            data['user_password'] = user_password
        
        # Replace placeholders in the message content
        message = template.message_content
        for key, value in data.items():
            placeholder = '{' + key + '}'
            message = message.replace(placeholder, str(value))
        
        # Add additional notes if provided
        if additional_notes:
            message += f"\n\nAdditional Notes: {additional_notes}"
        
        return message
    
    def _generate_default_message(self, shipment, message_type, include_tracking, include_sender, 
                                include_credentials=False, user_phone='', user_password='', additional_notes=''):
        """Fallback method to generate messages if no template is found in the database"""
        # Get sender country name
        sender_country = shipment.sender_country.name if shipment.sender_country else 'Unknown'
        recipient_country = shipment.recipient_country.name if hasattr(shipment, 'recipient_country') and shipment.recipient_country else 'Unknown'
        
        # Basic greeting and intro
        recipient_name = shipment.recipient_name.split()[0] if shipment.recipient_name else "Valued Customer"
        sender_name = getattr(shipment, 'sender_name', '')
        
        if message_type == 'sender_notification':
            message = f"Dear {sender_name},\n\n"
            message += f"Thank you for creating a shipment with Grade-A Express. Your shipment has been successfully registered in our system and is awaiting payment.\n\n"
            
            message += f"Shipment Details:\n"
            message += f"- Tracking Number: {getattr(shipment, 'tracking_number', '')}\n"
            message += f"- Package Type: {getattr(shipment, 'package_type', 'Package')}\n"
            message += f"- Weight: {getattr(shipment, 'weight', '')} kg\n"
            
            if all([hasattr(shipment, attr) for attr in ['length', 'width', 'height']]):
                message += f"- Dimensions: {shipment.length} × {shipment.width} × {shipment.height} cm\n"
            
            message += f"- Declared Value: ${getattr(shipment, 'declared_value', '0.00')}\n"
            message += f"- Total Cost: ${getattr(shipment, 'total_cost', '0.00')}\n\n"
            
            message += f"Recipient Information:\n"
            message += f"- Name: {getattr(shipment, 'recipient_name', '')}\n"
            message += f"- Country: {recipient_country}\n"
            message += f"- Address: {getattr(shipment, 'recipient_address', '')}\n"
            message += f"- Phone: {getattr(shipment, 'recipient_phone', '')}\n\n"
            
            # Get payment method and status
            payment_method = 'Online Payment'
            if hasattr(shipment, 'get_payment_method_display'):
                payment_method = shipment.get_payment_method_display()
            
            payment_status = 'Pending'
            if hasattr(shipment, 'get_payment_status_display'):
                payment_status = shipment.get_payment_status_display()
            
            message += f"Payment Information:\n"
            message += f"- Payment Method: {payment_method}\n"
            message += f"- Payment Status: {payment_status}\n\n"
            
            if include_credentials:
                # Get user phone from shipment if not provided
                if not user_phone and hasattr(shipment, 'user') and shipment.user:
                    user_phone = getattr(shipment.user, 'phone_number', '') or getattr(shipment.user, 'phone', '') or getattr(shipment.user, 'username', '')
                
                message += f"To complete your payment and proceed with shipping, please log in to your shipping panel using the following credentials:\n"
                if user_phone:
                    message += f"- Phone Number/Username: {user_phone}\n"
                if user_password:
                    message += f"- Password: {user_password}\n\n"
                
                message += f"You can access your shipping panel at: https://www.gradeaexpress.com/login\n\n"
                message += f"If you have already received your login details, please use those to access the system. Once logged in, navigate to \"My Shipments\" and select this shipment to complete the payment process.\n\n"
            else:
                message += f"To complete your payment and proceed with shipping, please log in to your shipping panel and navigate to \"My Shipments\".\n\n"
            
            message += f"If you have any questions or need assistance, please contact our customer support team."
            
        elif message_type == 'confirmation':
            message = f"Dear {recipient_name},\n\n"
            message += f"Your shipment has been confirmed and is now being processed. "
            
            if include_tracking:
                message += f"You can track your shipment using tracking number: {shipment.tracking_number}. "
            
            if include_sender:
                message += f"\n\nShipment Details:\n"
                message += f"- Sender: {shipment.sender_name}\n"
                message += f"- From: {sender_country}\n"
                message += f"- Package Type: {shipment.package_type}\n"
                message += f"- Weight: {shipment.weight} kg\n"
                message += f"- Dimensions: {shipment.length} × {shipment.width} × {shipment.height} cm\n"
                if hasattr(shipment, 'description') and shipment.description:
                    message += f"- Contents: {shipment.description}\n"
            
            message += f"\nEstimated delivery date: {shipment.estimated_delivery.strftime('%d %B %Y') if hasattr(shipment, 'estimated_delivery') and shipment.estimated_delivery else 'To be determined'}."
            
        elif message_type == 'notification':
            message = f"Dear {recipient_name},\n\n"
            message += f"We'd like to inform you that a package from {shipment.sender_name} in {sender_country} "
            message += f"is on its way to you. "
            
            if include_tracking:
                message += f"The tracking number for this shipment is: {shipment.tracking_number}.\n\n"
                status_display = shipment.get_status_display() if hasattr(shipment, 'get_status_display') else getattr(shipment, 'status', 'Processing')
                message += f"Current Status: {status_display}\n"
                message += f"Current Location: {getattr(shipment, 'current_location', 'In processing')}\n"
            
            if include_sender:
                message += f"\nShipment Origin: {sender_country}\n"
                if hasattr(shipment, 'sender_email') and hasattr(shipment, 'sender_phone'):
                    message += f"Sender Contact: {shipment.sender_email} / {shipment.sender_phone}\n"
            
            message += f"\nOur delivery team will contact you prior to delivery. Please ensure someone is available to receive the package."
            
        elif message_type == 'delivery':
            message = f"Dear {recipient_name},\n\n"
            message += f"Good news! Your package from {shipment.sender_name} in {sender_country} is out for delivery today. "
            message += f"Please ensure someone is available at the delivery address to receive the package.\n\n"
            
            if include_tracking:
                message += f"Tracking Number: {shipment.tracking_number}\n"
            
            if include_sender:
                message += f"Package Type: {getattr(shipment, 'package_type', 'Package')}\n"
                if hasattr(shipment, 'weight'):
                    message += f"Weight: {shipment.weight} kg\n"
            
            message += f"\nIf you have any special delivery instructions, please contact our customer service team immediately."
            
        else:  # custom message
            message = f"Dear {recipient_name},\n\n"
            message += f"We have an update regarding your shipment from {sender_country}. "
            
            if include_tracking:
                message += f"Tracking Number: {shipment.tracking_number}\n"
                status_display = shipment.get_status_display() if hasattr(shipment, 'get_status_display') else getattr(shipment, 'status', 'Processing')
                message += f"Current Status: {status_display}\n"
            
            if include_sender:
                message += f"\nSender: {shipment.sender_name}\n"
                message += f"Origin: {sender_country}\n"
            
            message += f"\nPlease check our website or tracking portal for more details."
        
        # Add additional notes if provided
        if additional_notes:
            message += f"\n\nAdditional Notes: {additional_notes}"
        
        # Add signature
        message += f"\n\nThank you for choosing Grade-A Express for your shipping needs.\n\n"
        message += f"Best regards,\nThe Grade-A Express Team"
        
        return message