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
                rate = WeightBasedRate.objects.get(
                    zone=shipping_zone,
                    service_type=service_type,
                    min_weight__lte=chargeable_weight,
                    max_weight__gte=chargeable_weight,
                    is_active=True
                )
                
                if not rate:
                    logger.warning(f"No rate found for weight {chargeable_weight}kg and service {service_type.name}")
                    raise ValidationError(f"No rate found for weight {chargeable_weight}kg and service {service_type.name}")
                    
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
        cost_breakdown['service_price'] = service_type.price
        
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
            extras_total = Decimal('0.00')
            try:
                for extra_data in extras_data:
                    if not isinstance(extra_data, dict):
                        continue
                        
                    extra_id = extra_data.get('id')
                    quantity = int(extra_data.get('quantity', 1))
                    
                    if not extra_id or quantity <= 0:
                        continue
                    
                    try:
                        extra = Extras.objects.get(id=extra_id, is_active=True)
                        
                        # Calculate charge
                        extra_charge = Decimal('0.00')
                        if extra.charge_type == 'FIXED':
                            extra_charge = extra.value * quantity
                        else:  # PERCENTAGE
                            # Apply percentage to weight charge + service charge
                            base_for_percentage = cost_breakdown['weight_charge'] + cost_breakdown['service_price']
                            extra_charge = (base_for_percentage * extra.value / 100) * quantity
                        
                        extra_charge = round(extra_charge, 2)
                        extras_total += extra_charge
                        
                        cost_breakdown['extras'].append({
                            'id': extra.id,
                            'name': extra.name,
                            'charge_type': extra.charge_type,
                            'value': float(extra.value),
                            'quantity': quantity,
                            'amount': float(extra_charge)
                        })
                    except Extras.DoesNotExist:
                        cost_breakdown['errors'].append(f"Extra with id {extra_id} does not exist or is not active")
                
                # Add extras total to cost breakdown
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
        fontSize=20,  # Reduced from 24
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=5,  # Reduced from 10
        alignment=TA_LEFT
    ))
    
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Heading2'],
        fontSize=12,  # Reduced from 14
        textColor=colors.HexColor('#424242'),
        spaceBefore=10,  # Reduced from 20
        spaceAfter=10,  # Reduced from 20
        alignment=TA_RIGHT
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading3'],
        fontSize=10,  # Reduced from 12
        textColor=colors.HexColor('#1a237e'),
        spaceBefore=10,  # Reduced from 15
        spaceAfter=5   # Reduced from 10
    ))
    

    # Create QR code with tracking URL
    tracking_url = f"https://www.gradeaexpress.com/tracking?tracking_number={shipment.tracking_number}"
    qr_code = create_qr_code(data=tracking_url, size=30*mm)  # Reduced from 40mm

    # Header with company info, receipt details, and QR code
    header_data = [
        [Paragraph("GRADE-A EXPRESS", styles['CompanyName']),
         Paragraph("SHIPPING RECEIPT", styles['ReceiptTitle']),
         qr_code],
        ["", f"Receipt Date: {shipment.created_at.strftime('%d/%m/%Y')}", ""],  # Changed date format
        ["", f"Tracking #: {shipment.tracking_number}", "Scan to track"]  # Shortened "Number" to "#"
    ]

    header_table = Table(header_data, colWidths=[3.5*inch, 3*inch, 1.2*inch])  # Adjusted widths
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (2, 0), (2, 0), 'TOP'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#424242')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),  # Reduced from 10
        ('FONTSIZE', (2, 2), (2, 2), 7),  # Reduced from 8
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),  # Reduced from 20
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))  # Reduced from 20

    # Status box with background color
    status_style = ParagraphStyle(
        'StatusStyle',
        parent=styles['Normal'],
        fontSize=11,  # Reduced from 12
        textColor=colors.white,
        alignment=TA_CENTER,
        backColor=colors.HexColor('#1a237e'),
        borderPadding=5  # Reduced from 10
    )
    elements.append(Paragraph(f"SHIPMENT STATUS: {shipment.get_status_display()}", status_style))
    elements.append(Spacer(1, 10))  # Reduced from 20

    # Tracking info with timeline style
    status_info = [
        ['Current Location:', shipment.current_location or 'N/A'],
        ['Est. Delivery:', shipment.estimated_delivery.strftime('%d/%m/%Y') if shipment.estimated_delivery else 'TBD']
    ]

    status_table = Table(status_info, colWidths=[1.3*inch, 6.4*inch])  # Adjusted widths
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced from 10
        ('TOPPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(status_table)
    elements.append(Spacer(1, 10))  # Reduced from 20

    # Shipping details with better styling
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
        ('FONTSIZE', (0, 1), (-1, -1), 9),  # Reduced from 10
        ('TOPPADDING', (0, 1), (-1, 1), 8),  # Reduced from 10
        ('BOTTOMPADDING', (0, 1), (-1, 1), 8),  # Reduced from 10
        ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#f8f9fa')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#f8f9fa')),
        ('BOX', (0, 1), (0, 1), 1, colors.HexColor('#dddddd')),
        ('BOX', (1, 1), (1, 1), 1, colors.HexColor('#dddddd')),
    ]))
    elements.append(shipping_table)
    elements.append(Spacer(1, 10))  # Reduced from 20

    # Package details
    elements.append(Paragraph('SHIPMENT DETAILS', styles['SectionHeader']))
    
    package_info = [
        ['Package Type:', shipment.package_type, 'Service:', shipment.service_type.name],  # Shortened "Service Type"
        ['Weight:', f"{shipment.weight} kg", 'Dimensions:', f"{shipment.length}x{shipment.width}x{shipment.height} cm"],
        ['Declared Value:', f"${shipment.declared_value:,.2f}", '', ''],
    ]

    package_table = Table(package_info, colWidths=[1.3*inch, 2.4*inch, 1.3*inch, 2.7*inch])
    package_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9f9f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#424242')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced from 10
        ('TOPPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
    ]))
    elements.append(package_table)
    elements.append(Spacer(1, 10))  # Reduced from 20

    # Cost breakdown
    elements.append(Paragraph('COST BREAKDOWN', styles['SectionHeader']))
    
    # Calculate subtotal (before COD and delivery charges)
    subtotal = (
        shipment.base_rate + 
        shipment.weight_charge + 
        shipment.service_charge +
        shipment.total_additional_charges
    )
    
    cost_data = [
        ['Base Rate:', f"${shipment.base_rate:,.2f}"],
        ['Weight Charge:', f"${shipment.weight_charge:,.2f}"],
        ['Service Charge:', f"${shipment.service_charge:,.2f}"],
        ['Additional Charges:', f"${shipment.total_additional_charges:,.2f}"],
        ['Subtotal:', f"${subtotal:,.2f}"],
    ]
    
    # Add COD charge if applicable
    if shipment.payment_method == 'COD' and shipment.cod_amount > 0:
        cost_data.append(['COD Charge (5%):', f"${shipment.cod_amount:,.2f}"])
    
    # Add delivery charge
    cost_data.append(['Delivery Charge:', f"${shipment.delivery_charge:,.2f}"])
    
    # Add total cost as the final row
    cost_data.append(['Total Cost:', f"${shipment.total_cost:,.2f}"])

    cost_table = Table(cost_data, colWidths=[5.7*inch, 2*inch])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -3), colors.HexColor('#f9f9f9')),  # All rows except subtotal, delivery charge and total
        ('BACKGROUND', (0, -3), (-1, -3), colors.HexColor('#f0f0f0')),  # Subtotal row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1a237e')),  # Total row
        ('TEXTCOLOR', (0, 0), (-1, -2), colors.HexColor('#424242')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -4), 'Helvetica'),  # Regular font for base items
        ('FONTNAME', (0, -3), (-1, -2), 'Helvetica-Bold'),  # Bold for subtotal and delivery charge
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold for total
        ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced from 10
        ('TOPPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),  # Reduced from 8
        ('LEFTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),  # Reduced from 10
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#dddddd')),
        ('BOX', (0, -1), (-1, -1), 1, colors.white),
    ]))
    elements.append(cost_table)

    # Footer
    footer_text = f"""Thank you for choosing Grade-A Express! | Track your shipment: {shipment.tracking_number}"""
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,  # Reduced from 9
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        spaceBefore=15,  # Reduced from 30
        borderColor=colors.HexColor('#dddddd'),
        borderWidth=1,
        borderPadding=5,  # Reduced from 10
        borderRadius=3  # Reduced from 5
    )
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf 

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
        ['Service Charge:', f"${service_charge}"],
        ['Weight Charge:', f"${weight_charge}"],
        ['Additional Charges:', f"${total_additional_charges}"],
        ['Extras Charges:', f"${extras_charges}"],
    ]
    
    # Add delivery charge if present
    if shipment.delivery_charge and shipment.delivery_charge > 0:
        table_data.append(['Delivery Charge:', f"${delivery_charge}"])
    
    # Add COD charge if present
    if shipment.cod_amount and shipment.cod_amount > 0:
        table_data.append(['COD Fee:', f"${cod_amount}"])
    
    # Add total
    table_data.append(['Total:', f"${total_cost}"])
    
    return table_data 