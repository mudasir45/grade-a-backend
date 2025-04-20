import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.conf import settings
# Import models
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

# Set up logger
logger = logging.getLogger(__name__)

# Don't import models at the module level to avoid circular imports
# Instead, import them inside the functions where needed

def format_decimal(value, decimal_places=2):
    """Format a decimal value with commas as thousand separators and fixed decimal places"""
    if value is None:
        return "0.00"
    try:
        # Ensure value is a Decimal
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Format with commas and fixed decimal places
        formatted = f"{value:,.{decimal_places}f}"
        return formatted
    except (ValueError, TypeError, InvalidOperation):
        return "0.00"

def calculate_shipping_cost(
    sender_country_id=None,
    recipient_country_id=None,
    service_type_id=None,
    weight=None,
    dimensions=None,
    city_id=None,
    extras_data=None
):
    """
    Calculate shipping cost based on provided parameters
    Returns a cost breakdown dictionary with all details
    """
    # Import models inside function to avoid circular imports
    from accounts.models import City
    from shipping_rates.models import (AdditionalCharge, DimensionalFactor,
                                       ServiceType, ShippingZone,
                                       WeightBasedRate)

    from .models import Country, Extras

    # Initialize cost breakdown dictionary
    cost_breakdown = {
        'weight_charge': Decimal('0.00'),
        'service_price': Decimal('0.00'),
        'city_delivery_charge': Decimal('0.00'),
        'additional_charges': [],
        'extras': [],
        'total_cost': Decimal('0.00'),
        'errors': [],
        'volumetric_weight': Decimal('0.00'),
        'chargeable_weight': Decimal('0.00')
    }
    
    try:
        # First check if we have dimensions to calculate volumetric weight
        volumetric_weight = None
        if dimensions and all(key in dimensions for key in ['length', 'width', 'height']):
            try:
                # Get dimensional factor for the service type
                service_type = ServiceType.objects.get(id=service_type_id, is_active=True)
                dim_factor = DimensionalFactor.objects.filter(
                    service_type=service_type,
                    is_active=True
                ).first()
                
                if dim_factor:
                    # Calculate volumetric weight
                    length = Decimal(str(dimensions.get('length', 0)))
                    width = Decimal(str(dimensions.get('width', 0)))
                    height = Decimal(str(dimensions.get('height', 0)))
                    
                    if all([length > 0, width > 0, height > 0]):
                        volumetric_weight = (length * width * height) / Decimal(str(dim_factor.factor))
                        cost_breakdown['volumetric_weight'] = volumetric_weight
                        logger.info(f"Calculated volumetric weight: {volumetric_weight}kg")
            except Exception as e:
                logger.warning(f"Error calculating volumetric weight: {str(e)}")

        # Validate required parameters
        if not all([sender_country_id, recipient_country_id, service_type_id]) or (weight is None and volumetric_weight is None):
            cost_breakdown['errors'].append("Missing required parameters")
            return cost_breakdown
        
        # Use volumetric weight if it's greater than actual weight or if actual weight is not provided
        if weight is not None:
            try:
                weight = Decimal(str(weight))
            except (InvalidOperation, TypeError):
                cost_breakdown['errors'].append("Invalid weight format")
                return cost_breakdown
        
        # Determine the chargeable weight
        chargeable_weight = weight if weight is not None else Decimal('0.00')
        if volumetric_weight and (weight is None or volumetric_weight > chargeable_weight):
            chargeable_weight = volumetric_weight
            logger.info(f"Using volumetric weight: {volumetric_weight}kg instead of actual weight: {weight}kg")
        
        cost_breakdown['chargeable_weight'] = chargeable_weight
        
        # Get the service type
        try:
            service_type = ServiceType.objects.get(id=service_type_id, is_active=True)
        except ServiceType.DoesNotExist:
            cost_breakdown['errors'].append(f"Service type with id {service_type_id} does not exist or is not active")
            return cost_breakdown
        
        # Find applicable shipping zone
        try:
            sender_country = Country.objects.get(id=sender_country_id, is_active=True)
            recipient_country = Country.objects.get(id=recipient_country_id, is_active=True)
            
            # Get shipping zones that include both sender and recipient countries
            shipping_zones = ShippingZone.objects.filter(
                departure_countries=sender_country,
                destination_countries=recipient_country,
                is_active=True
            )
            
            if not shipping_zones.exists():
                cost_breakdown['errors'].append(
                    f"No shipping zone found for {sender_country.name} to {recipient_country.name}"
                )
                return cost_breakdown
                
            # Use the first applicable shipping zone
            shipping_zone = shipping_zones.first()
            
            # Get applicable rate based on weight
            try:
                # Use filter instead of get to handle multiple matching rates
                rates = WeightBasedRate.objects.filter(
                    zone=shipping_zone,
                    service_type=service_type,
                    min_weight__lte=chargeable_weight,
                    max_weight__gte=chargeable_weight,
                    is_active=True
                )
                
                if not rates.exists():
                    logger.warning(f"No rate found for weight {chargeable_weight}kg and service {service_type.name}")
                    raise ValidationError(f"No rate found for weight {chargeable_weight}kg and service {service_type.name}")
                
                # If multiple rates exist, select the most specific one (narrowest weight range)
                if rates.count() > 1:
                    # Order by the smaller weight range (max_weight - min_weight)
                    rate = sorted(rates, key=lambda r: (r.max_weight - r.min_weight))[0]
                    logger.info(f"Multiple rates found, selected most specific one: {rate}")
                else:
                    rate = rates.first()
                
                # Ensure we have a valid rate
                if rate is None:
                    raise ValidationError("Failed to retrieve a valid rate after filtering")
                    
                # Calculate base weight charge
                weight_charge = chargeable_weight * rate.per_kg_rate
                cost_breakdown['weight_charge'] = round(weight_charge, 2)
                
                # Add per kg rate for reference
                cost_breakdown['per_kg_rate'] = rate.per_kg_rate
            except Exception as e:
                cost_breakdown['errors'].append(f"Error finding rate: {str(e)}")
        except Country.DoesNotExist:
            cost_breakdown['errors'].append(f"One or more countries not found or not active")
            return cost_breakdown
        except Exception as e:
            cost_breakdown['errors'].append(f"Error finding shipping zone: {str(e)}")
            return cost_breakdown
        
        # Add service price
        # cost_breakdown['service_price'] = service_type.price
        
        # Add city delivery charge if city is provided
        if city_id:
            try:
                city = City.objects.get(id=city_id, is_active=True)
                cost_breakdown['city_delivery_charge'] = city.delivery_charge
            except City.DoesNotExist:
                cost_breakdown['errors'].append(f"City with id {city_id} does not exist or is not active")
        
        # Process additional charges
        if shipping_zone and service_type:
            try:
                # Log the shipping zone and service type for debugging
                logger.info(f"Fetching additional charges for zone={shipping_zone.id}, service_type={service_type.id}")
                
                # Get all applicable additional charges
                additional_charges = AdditionalCharge.objects.filter(
                    zones=shipping_zone,
                    service_types=service_type,
                    is_active=True
                )
                
                # Log how many charges were found
                logger.info(f"Found {additional_charges.count()} active additional charges")
                
                for charge in additional_charges:
                    charge_amount = Decimal('0.00')
                    if charge.charge_type == 'FIXED':
                        charge_amount = charge.value
                        logger.info(f"Applied FIXED charge: {charge.name}, value={charge.value}")
                    else:  # PERCENTAGE
                        charge_amount = (cost_breakdown['weight_charge'] * charge.value / 100)
                        logger.info(f"Applied PERCENTAGE charge: {charge.name}, value={charge.value}%, base={cost_breakdown['weight_charge']}")
                    
                    charge_amount = round(charge_amount, 2)
                    logger.info(f"Charge amount for {charge.name}: {charge_amount}")
                    
                    cost_breakdown['additional_charges'].append({
                        'id': charge.id,
                        'name': charge.name,
                        'type': charge.charge_type,
                        'value': float(charge.value),
                        'amount': float(charge_amount)
                    })
                
                # Calculate and log total additional charges
                total_additional = sum(Decimal(str(charge['amount'])) for charge in cost_breakdown['additional_charges'])
                logger.info(f"Total additional charges: {total_additional}")
                
            except Exception as e:
                error_msg = f"Error processing additional charges: {str(e)}"
                logger.error(error_msg, exc_info=True)
                cost_breakdown['errors'].append(error_msg)
                
        # Process extras if provided
        if extras_data:
            # Split extras into fixed and percentage types
            fixed_extras = []
            percentage_extras = []
            fixed_extras_total = Decimal('0.00')
            
            try:
                # First, categorize extras into fixed and percentage types
                for extra_data in extras_data:
                    if not isinstance(extra_data, dict):
                        continue
                        
                    extra_id = extra_data.get('id')
                    quantity = int(extra_data.get('quantity', 1))
                    
                    if not extra_id or quantity <= 0:
                        continue
                    
                    try:
                        extra = Extras.objects.get(id=extra_id, is_active=True)
                        
                        # Store the extra info for later processing
                        if extra.charge_type == 'FIXED':
                            fixed_extras.append({
                                'extra': extra,
                                'quantity': quantity
                            })
                        else:  # PERCENTAGE
                            percentage_extras.append({
                                'extra': extra,
                                'quantity': quantity
                            })
                    except Extras.DoesNotExist:
                        cost_breakdown['errors'].append(f"Extra with id {extra_id} does not exist or is not active")
                
                # Process fixed extras first
                for item in fixed_extras:
                    extra = item['extra']
                    quantity = item['quantity']
                    
                    # Calculate fixed charge
                    extra_charge = extra.value * quantity
                    extra_charge = round(extra_charge, 2)
                    fixed_extras_total += extra_charge
                    
                    # Add to cost breakdown
                    cost_breakdown['extras'].append({
                        'id': extra.id,
                        'name': extra.name,
                        'charge_type': extra.charge_type,
                        'value': float(extra.value),
                        'quantity': quantity,
                        'amount': float(extra_charge)
                    })
                
                # Calculate subtotal including fixed extras
                subtotal = (
                    cost_breakdown['weight_charge'] +
                    cost_breakdown['service_price'] +
                    cost_breakdown['city_delivery_charge']
                )
                
                # Add additional charges to subtotal
                for charge in cost_breakdown['additional_charges']:
                    subtotal += Decimal(str(charge['amount']))
                
                # Add fixed extras to subtotal
                subtotal += fixed_extras_total
                
                # Now process percentage extras based on the subtotal
                percentage_extras_total = Decimal('0.00')
                for item in percentage_extras:
                    extra = item['extra']
                    quantity = item['quantity']
                    
                    # Calculate percentage charge based on subtotal
                    extra_charge = (subtotal * extra.value / 100) * quantity
                    extra_charge = round(extra_charge, 2)
                    percentage_extras_total += extra_charge
                    
                    # Add to cost breakdown
                    cost_breakdown['extras'].append({
                        'id': extra.id,
                        'name': extra.name,
                        'charge_type': extra.charge_type,
                        'value': float(extra.value),
                        'quantity': quantity,
                        'amount': float(extra_charge)
                    })
                
                # Calculate final extras total
                extras_total = fixed_extras_total + percentage_extras_total
                cost_breakdown['extras_total'] = extras_total
                
            except Exception as e:
                cost_breakdown['errors'].append(f"Error processing extras: {str(e)}")
                
        # Calculate total cost
        total_cost = (
            cost_breakdown['weight_charge'] +
            cost_breakdown['service_price'] +
            cost_breakdown['city_delivery_charge']
        )
        
        # Add additional charges to total
        for charge in cost_breakdown['additional_charges']:
            total_cost += Decimal(str(charge['amount']))
            
        # Add extras to total
        if 'extras_total' in cost_breakdown:
            total_cost += cost_breakdown['extras_total']
        
        cost_breakdown['total_cost'] = round(total_cost, 2)
    
    except ValidationError as e:
        cost_breakdown['errors'].append(f"Validation error: {str(e)}")
    except ObjectDoesNotExist as e:
        cost_breakdown['errors'].append(f"Object not found: {str(e)}")
    except Exception as e:
        cost_breakdown['errors'].append(f"Unexpected error: {str(e)}")
    
    return cost_breakdown

def create_qr_code(data, size=40*mm):
    """Create a QR code for the tracking number."""
    qr_code = QrCodeWidget(data)
    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size/width, 0, 0, size/height, 0, 0])
    drawing.add(qr_code)
    return drawing

def generate_shipment_receipt(shipment):
    """Generate a professional PDF receipt for a shipment."""
    buffer = BytesIO()
    # Use A4 for standard business documents
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=20,
        bottomMargin=20
    )

    # Collect the elements
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='CompanyName',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=10,
        alignment=TA_LEFT
    ))
    
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#424242'),
        spaceBefore=20,
        spaceAfter=20,
        alignment=TA_RIGHT
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#1a237e'),
        spaceBefore=15,
        spaceAfter=10
    ))

    # Create QR code with tracking URL
    tracking_url = f"https://www.gradeaexpress.com/tracking?tracking_number={shipment.tracking_number}"
    qr_code = create_qr_code(data=tracking_url, size=30*mm)

    # Header with company info and receipt details
    header_data = [
        [Paragraph("GRADE-A EXPRESS", styles['CompanyName']),
         Paragraph("SHIPPING RECEIPT", styles['ReceiptTitle']),
         qr_code],
        ["", f"Receipt Date: {shipment.created_at.strftime('%d/%m/%Y')}", ""],
        ["", "", "Scan to track"]
    ]

    header_table = Table(header_data, colWidths=[3.5*inch, 3*inch, 1.2*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (2, 0), (2, 0), 'TOP'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#424242')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('FONTSIZE', (2, 2), (2, 2), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 20),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Tracking number in a colored box
    tracking_style = ParagraphStyle(
        'TrackingStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.white,
        alignment=TA_CENTER,
        backColor=colors.HexColor('#1a237e'),
        borderPadding=10,
        borderRadius=5
    )
    
    # Add package numbering information (1/{no_of_packages})
    package_info = ""
    if hasattr(shipment, 'no_of_packages') and shipment.no_of_packages > 1:
        package_info = f" - Package 1/{shipment.no_of_packages}"
    
    elements.append(Paragraph(f"TRACKING NUMBER: {shipment.tracking_number}{package_info}", tracking_style))
    elements.append(Spacer(1, 20))

    # Shipping details
    shipping_data = [
        [Paragraph('FROM:', styles['SectionHeader']), 
         Paragraph('TO:', styles['SectionHeader'])],
        [
            f"{shipment.sender_name}\n{shipment.sender_address}\n{shipment.sender_country.name}\nTel: {shipment.sender_phone}",
            f"{shipment.recipient_name}\n{shipment.recipient_address}\n{shipment.recipient_country.name}\nTel: {shipment.recipient_phone}"
        ]
    ]

    shipping_table = Table(shipping_data, colWidths=[3.85*inch, 3.85*inch])
    shipping_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#424242')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, 1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#f8f9fa')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#f8f9fa')),
        ('BOX', (0, 1), (0, 1), 1, colors.HexColor('#dddddd')),
        ('BOX', (1, 1), (1, 1), 1, colors.HexColor('#dddddd')),
    ]))
    elements.append(shipping_table)
    elements.append(Spacer(1, 20))

    # Package details
    elements.append(Paragraph('SHIPMENT DETAILS', styles['SectionHeader']))
    
    # Use the existing format_decimal function
    formatted_declared_value = f"MYR {format_decimal(shipment.declared_value)}"
    
    package_info = [
        ['Package Type:', shipment.package_type, 'Service:', shipment.service_type.name],  # Shortened "Service Type"
        ['Weight:', f"{shipment.weight} kg", 'Dimensions:', f"{shipment.length}x{shipment.width}x{shipment.height} cm"],
        ['Declared Value:', formatted_declared_value, '', ''],
    ]
    
    # Add package number information if there are multiple packages
    if hasattr(shipment, 'no_of_packages') and shipment.no_of_packages > 1:
        package_info.append(['Package Number:', f"1/{shipment.no_of_packages}", '', ''])

    package_table = Table(package_info, colWidths=[1.3*inch, 2.4*inch, 1.3*inch, 2.7*inch])
    package_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9f9f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
    ]))
    elements.append(package_table)
    elements.append(Spacer(1, 20))

    # Cost breakdown
    elements.append(Paragraph('COST BREAKDOWN', styles['SectionHeader']))
    
    # Use the existing format_decimal function for all currency values
    cost_data = [
        ['Weight Charge:', f"MYR {format_decimal(shipment.weight_charge)}"],
        ['Mandatory Charges:', f"MYR {format_decimal(shipment.total_additional_charges)}"],
        ['Additional Charges:', f"MYR {format_decimal(shipment.extras_charges)}"],
        ['Delivery Charge:', f"MYR {format_decimal(shipment.delivery_charge)}"]
    ]

    # Add COD charge if applicable
    if shipment.payment_method == 'COD' and shipment.cod_amount > 0:
        # Get the dynamic COD percentage
        try:
            # Import here to avoid circular imports
            from shipping_rates.models import DynamicRate
            cod_rate = DynamicRate.objects.filter(
                rate_type='COD_FEE', 
                charge_type='PERCENTAGE',
                is_active=True
            ).first()
            cod_percentage = cod_rate.value if cod_rate else 5  # Default to 5% if not found
        except Exception:
            cod_percentage = 5  # Default to 5% if error occurs
            
        cost_data.append([f'COD Charge ({cod_percentage}%):', f"MYR {format_decimal(shipment.cod_amount)}"])

    # Add total cost as the final row
    cost_data.append(['Total Cost:', f"MYR {format_decimal(shipment.total_cost)}"])

    cost_table = Table(cost_data, colWidths=[5.7*inch, 2*inch])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), colors.HexColor('#f9f9f9')),  # All rows except total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1a237e')),  # Total row
        ('TEXTCOLOR', (0, 0), (-1, -2), colors.HexColor('#424242')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),  # Regular font for base items
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold for total
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#dddddd')),
        ('BOX', (0, -1), (-1, -1), 1, colors.white),
    ]))
    elements.append(cost_table)
    
    # Add Extras Details section if extras are associated with the shipment
    shipment_extras = shipment.shipmentextras_set.all()
    if shipment_extras.exists():
        elements.append(Spacer(1, 15))
        elements.append(Paragraph('ADDITIONAL SERVICES DETAILS', styles['SectionHeader']))
        
        extras_data = [
            ['Service', 'Description', 'Quantity', 'Cost']
        ]
        
        for extra_item in shipment_extras:
            extra_cost = 0
            if extra_item.extra.charge_type == 'FIXED':
                extra_cost = extra_item.extra.value * extra_item.quantity
            else:  # PERCENTAGE
                # For percentage based extras, calculate based on appropriate base
                base_cost = shipment.weight_charge
                extra_cost = (base_cost * extra_item.extra.value / 100) * extra_item.quantity
            
            extras_data.append([
                extra_item.extra.name,
                extra_item.extra.description,
                str(extra_item.quantity),
                f"MYR {format_decimal(extra_cost)}"
            ])
        
        extras_table = Table(extras_data, colWidths=[1.5*inch, 3.5*inch, 0.7*inch, 1*inch])
        extras_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),  # Header row
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#424242')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (2, 1), (3, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ]))
        elements.append(extras_table)

    # Footer
    package_info = ""
    if hasattr(shipment, 'no_of_packages') and shipment.no_of_packages > 1:
        package_info = f" (Package 1/{shipment.no_of_packages})"
    
    footer_text = f"""Thank you for choosing Grade-A Express! | Track your shipment: {shipment.tracking_number}{package_info}"""
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        spaceBefore=30,
        borderColor=colors.HexColor('#dddddd'),
        borderWidth=1,
        borderPadding=10,
        borderRadius=5
    )
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_tracking_number():
    """Generate a unique tracking number for shipments"""
    prefix = 'TRK'
    random_digits = get_random_string(9, '0123456789')
    tracking_number = f"{prefix}{random_digits}"
    
    # Add initial tracking entry
    tracking_history = [{
        'status': 'PENDING',
        'location': 'Order Received',
        'timestamp': timezone.now().isoformat(),
        'description': 'Shipment request created'
    }]
    
    return tracking_number 

def generate_receipt_table_data(shipment):
    """Generate data for receipt PDF table"""
    # Format monetary values with commas and 2 decimal places
    service_charge = format_decimal(shipment.service_charge)
    weight_charge = format_decimal(shipment.weight_charge)
    total_additional_charges = format_decimal(shipment.total_additional_charges)
    extras_charges = format_decimal(shipment.extras_charges)
    delivery_charge = format_decimal(shipment.delivery_charge)
    cod_amount = format_decimal(shipment.cod_amount)
    total_cost = format_decimal(shipment.total_cost)
    
    # Build table data
    table_data = [
        ['Item', 'Amount'],
        ['Service Charge:', f"MYR {service_charge}"],
        ['Weight Charge:', f"MYR {weight_charge}"],
        ['Mandatory Charges:', f"MYR {total_additional_charges}"],
        ['Additional Charges:', f"MYR {extras_charges}"],
    ]
    
    # Add delivery charge if present
    if shipment.delivery_charge and shipment.delivery_charge > 0:
        table_data.append(['Delivery Charge:', f"MYR {delivery_charge}"])
    
    # Add COD charge if present
    if shipment.cod_amount and shipment.cod_amount > 0:
        # Get the dynamic COD percentage
        try:
            from shipping_rates.models import DynamicRate
            cod_rate = DynamicRate.objects.filter(
                rate_type='COD_FEE', 
                charge_type='PERCENTAGE',
                is_active=True
            ).first()
            cod_percentage = cod_rate.value if cod_rate else 5  # Default to 5% if not found
        except Exception:
            cod_percentage = 5  # Default to 5% if error occurs
            
        table_data.append([f'COD Fee ({cod_percentage}%):', f"MYR {cod_amount}"])
    
    # Add total
    table_data.append(['Total:', f"MYR {total_cost}"])
    
    return table_data 