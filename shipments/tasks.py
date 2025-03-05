from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import SupportTicket


@shared_task
def send_ticket_creation_email_to_user(ticket_id):
    """Send confirmation email to user when ticket is created"""
    try:
        ticket = SupportTicket.objects.select_related('user').get(id=ticket_id)
        
        # Prepare email content
        context = {
            'ticket': ticket,
            'user': ticket.user,
            'support_email': settings.SUPPORT_EMAIL
        }
        
        html_message = render_to_string(
            'emails/support/ticket_created_user.html',
            context
        )
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=f'Support Ticket #{ticket.ticket_number} Created',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user.email],
            html_message=html_message
        )
        
        return True
    except Exception as e:
        print(f"Error sending ticket creation email to user: {str(e)}")
        return False

@shared_task
def send_ticket_creation_email_to_staff(ticket_id):
    """Notify staff about new support ticket"""
    try:
        ticket = SupportTicket.objects.select_related(
            'user',
            'shipment'
        ).get(id=ticket_id)
        
        # Prepare email content
        context = {
            'ticket': ticket,
            'user': ticket.user,
            'admin_url': f"{settings.ADMIN_URL}shipments/supportticket/{ticket.id}/change/"
        }
        
        html_message = render_to_string(
            'emails/support/ticket_created_staff.html',
            context
        )
        plain_message = strip_tags(html_message)
        
        # Send email to all staff users
        staff_emails = list(
            User.objects.filter(is_staff=True).values_list('email', flat=True)
        )
        
        if staff_emails:
            send_mail(
                subject=f'New Support Ticket: #{ticket.ticket_number}',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=staff_emails,
                html_message=html_message
            )
        
        return True
    except Exception as e:
        print(f"Error sending ticket creation email to staff: {str(e)}")
        return False

@shared_task
def send_ticket_status_update_email(ticket_id):
    """Send email notification when ticket status is updated"""
    try:
        ticket = SupportTicket.objects.select_related(
            'user',
            'assigned_to'
        ).get(id=ticket_id)
        
        # Prepare email content
        context = {
            'ticket': ticket,
            'user': ticket.user,
            'status': ticket.get_status_display(),
            'support_email': settings.SUPPORT_EMAIL
        }
        
        html_message = render_to_string(
            'emails/support/ticket_status_updated.html',
            context
        )
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=f'Support Ticket #{ticket.ticket_number} Status Updated',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user.email],
            html_message=html_message
        )
        
        return True
    except Exception as e:
        print(f"Error sending ticket status update email: {str(e)}")
        return False 