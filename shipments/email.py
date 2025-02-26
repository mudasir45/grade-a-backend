from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .utils import generate_shipment_receipt

def send_shipment_created_email(shipment):
    """
    Send shipment creation notification to all parties (admin, sender, and recipient)
    """
    # Generate receipt PDF
    receipt_pdf = generate_shipment_receipt(shipment)
    
    # Common context for email template
    context = {'shipment': shipment}
    
    # Render HTML content
    html_content = render_to_string('emails/shipment_created.html', context)
    text_content = strip_tags(html_content)
    
    # Create base email message
    subject = f'Shipment Created - Tracking #{shipment.tracking_number}'
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Send to admin
    admin_email = EmailMultiAlternatives(
        f'[ADMIN] {subject}',
        text_content,
        from_email,
        [settings.ADMIN_EMAIL]
    )
    admin_email.attach_alternative(html_content, "text/html")
    admin_email.attach(f'shipment_{shipment.tracking_number}.pdf', receipt_pdf, 'application/pdf')
    admin_email.send()
    
    # Send to sender
    sender_email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [shipment.sender_email]
    )
    sender_email.attach_alternative(html_content, "text/html")
    sender_email.attach(f'shipment_{shipment.tracking_number}.pdf', receipt_pdf, 'application/pdf')
    sender_email.send()
    
    # Send to recipient
    recipient_email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [shipment.recipient_email]
    )
    recipient_email.attach_alternative(html_content, "text/html")
    recipient_email.attach(f'shipment_{shipment.tracking_number}.pdf', receipt_pdf, 'application/pdf')
    recipient_email.send()

def send_status_update_email(shipment):
    """
    Send status update notification to sender and recipient
    """
    context = {'shipment': shipment}
    
    # Render HTML content
    html_content = render_to_string('emails/status_update.html', context)
    text_content = strip_tags(html_content)
    
    # Create base email message
    subject = f'Shipment Status Update - {shipment.get_status_display()} - Tracking #{shipment.tracking_number}'
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Send to sender
    sender_email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [shipment.sender_email]
    )
    sender_email.attach_alternative(html_content, "text/html")
    sender_email.send()
    
    # Send to recipient
    recipient_email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [shipment.recipient_email]
    )
    recipient_email.attach_alternative(html_content, "text/html")
    recipient_email.send() 