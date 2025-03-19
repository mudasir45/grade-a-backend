import os
from datetime import datetime
from io import BytesIO

from django.conf import settings
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
    tracking_url = f"https://grade-a-express.com/tracking?tracking_number={shipment.tracking_number}"
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