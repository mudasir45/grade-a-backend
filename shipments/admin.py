from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from accounts.models import DriverProfile, User

from .models import ShipmentRequest, ShipmentStatusLocation, SupportTicket


class StaffAssignmentFilter(admin.SimpleListFilter):
    """Filter shipments by whether they have a staff member assigned"""
    title = 'Staff Assignment'
    parameter_name = 'has_staff'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has staff assigned'),
            ('no', 'No staff assigned'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(staff=None)
        if self.value() == 'no':
            return queryset.filter(staff=None)
        return queryset


class DriverFilter(admin.SimpleListFilter):
    """Filter shipments by driver status"""
    title = 'Driver'
    parameter_name = 'driver'
    
    def lookups(self, request, model_admin):
        # Get all active drivers
        drivers = User.objects.filter(
            driver_profile__is_active=True
        ).values_list('id', 'email')
        return [('none', 'No driver')] + [(str(id), email) for id, email in drivers]
    
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(driver=None)
        if self.value():
            return queryset.filter(driver_id=self.value())
        return queryset


@admin.register(ShipmentStatusLocation)
class ShipmentStatusLocationAdmin(admin.ModelAdmin):
    """Admin interface for managing shipment status locations"""
    list_display = [
        'status_type', 'location_name', 'description', 
        'is_active', 'display_order'
    ]
    list_filter = ['status_type', 'is_active']
    search_fields = ['location_name', 'description']
    ordering = ['display_order', 'status_type']
    list_editable = ['is_active', 'display_order']


@admin.register(ShipmentRequest)
class ShipmentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_number', 'status_badge', 'payment_status_badge',
        'user_link', 'staff_link', 'driver_link', 'sender_name', 'recipient_name',
        'service_type', 'total_cost_display', 'receipt_download', 'created_at'
    ]
    list_filter = [
        'status', 'payment_method', 'payment_status',
        'service_type', 'created_at', StaffAssignmentFilter, DriverFilter
    ]
    search_fields = [
        'tracking_number', 'sender_name', 'recipient_name', 
        'current_location', 'user__email', 'staff__email',
        'driver__email', 'transaction_id'
    ]
    readonly_fields = [
        'tracking_number', 'tracking_history',
        'created_at', 'updated_at', 'receipt_download',
        'cod_amount', 'total_cost'
    ]
    
    actions = [
        'assign_to_me',
        'unassign_staff',
        'mark_payment_as_paid',
        'mark_payment_as_failed',
        'assign_to_driver',
        'unassign_driver'
    ]
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'user',
                ('staff', 'driver')
            )
        }),
        ('Tracking Information', {
            'fields': (
                'tracking_number', 'status', 'current_location',
                'estimated_delivery', 'tracking_history', 'receipt_download'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_method', 'payment_status', 'payment_date',
                'transaction_id', 'cod_amount'
            )
        }),
        ('Sender Information', {
            'fields': (
                'sender_name', 'sender_email', 'sender_phone',
                'sender_address', 'sender_country'
            )
        }),
        ('Recipient Information', {
            'fields': (
                'recipient_name', 'recipient_email', 'recipient_phone',
                'recipient_address', 'recipient_country'
            )
        }),
        ('Package Details', {
            'fields': (
                'package_type', 'weight', 'length', 'width', 'height',
                'description', 'declared_value'
            )
        }),
        ('Service Options', {
            'fields': (
                'service_type', 'insurance_required',
                'signature_required'
            )
        }),
        ('Cost Information', {
            'fields': (
                'base_rate', 'per_kg_rate', 'weight_charge',
                'service_charge', 'total_additional_charges',
                'total_cost'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'staff' in form.base_fields:
            # Limit staff field to only show staff members
            form.base_fields['staff'].queryset = User.objects.filter(
                is_staff=True
            ).exclude(user_type='DRIVER')
            form.base_fields['staff'].label = "Assign Staff"
        if 'driver' in form.base_fields:
            # Limit driver field to only show active drivers
            form.base_fields['driver'].queryset = User.objects.filter(
                driver_profile__is_active=True,
                user_type='DRIVER'
            )
            form.base_fields['driver'].label = "Assign Driver"
        return form
    
    def staff_link(self, obj):
        if obj.staff:
            try:
                app_label = obj.staff._meta.app_label
                model_name = obj.staff._meta.model_name
                url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.staff.id])
                return format_html('<a href="{}">{}</a>', url, obj.staff.email)
            except:
                return obj.staff.email
        return "-"
    staff_link.short_description = 'Staff'
    
    def driver_link(self, obj):
        if obj.driver:
            try:
                app_label = obj.driver._meta.app_label
                model_name = obj.driver._meta.model_name
                url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.driver.id])
                return format_html('<a href="{}">{}</a>', url, obj.driver.email)
            except:
                return obj.driver.email
        return "-"
    driver_link.short_description = 'Driver'
    
    def assign_to_me(self, request, queryset):
        """Assign selected shipments to the current user if they have staff status"""
        if not request.user.is_staff:
            self.message_user(
                request, 
                "You cannot assign shipments to yourself because you don't have staff status.",
                messages.ERROR
            )
            return
            
        updated = queryset.update(staff=request.user)
        self.message_user(request, f"{updated} shipments assigned to you.")
    assign_to_me.short_description = "Assign selected shipments to me"
    
    def unassign_staff(self, request, queryset):
        updated = queryset.update(staff=None)
        self.message_user(request, f"{updated} shipments unassigned from staff.")
    unassign_staff.short_description = "Unassign staff from selected shipments"
    
    def unassign_driver(self, request, queryset):
        updated = queryset.update(driver=None)
        self.message_user(request, f"{updated} shipments unassigned from driver.")
    unassign_driver.short_description = "Unassign driver from selected shipments"
    
    def assign_to_driver(self, request, queryset):
        """Action to assign selected shipments to a driver"""
        if request.POST.get('driver_id'):
            driver_id = request.POST.get('driver_id')
            try:
                driver = User.objects.get(
                    id=driver_id,
                    driver_profile__is_active=True,
                    user_type='DRIVER'
                )
                updated = queryset.update(driver=driver)
                self.message_user(
                    request,
                    f"{updated} shipments assigned to driver {driver.email}",
                    messages.SUCCESS
                )
                return None
            except User.DoesNotExist:
                self.message_user(
                    request,
                    "Selected driver not found or is not active",
                    messages.ERROR
                )
                return None
        
        # Get all active drivers
        drivers = User.objects.filter(
            driver_profile__is_active=True,
            user_type='DRIVER'
        ).values_list('id', 'email')
        
        if not drivers:
            self.message_user(
                request,
                "No active drivers found in the system.",
                messages.ERROR
            )
            return None
        
        # Create the HTML for the driver selection form
        driver_options = "\n".join(
            f'<option value="{id}">{email}</option>'
            for id, email in drivers
        )
        
        # Return a custom admin action page
        return format_html("""
            <form action="" method="post">
                <input type="hidden" name="action" value="assign_to_driver" />
                <input type="hidden" name="_selected_action" value="{}" />
                {}
                <p>Select a driver to assign the selected shipments to:</p>
                <select name="driver_id">
                    {}
                </select>
                <input type="submit" value="Assign Driver" />
            </form>
        """,
        ",".join(str(obj.pk) for obj in queryset),
        request.POST.get('csrfmiddlewaretoken', ''),
        driver_options
        )
    
    def user_link(self, obj):
        if obj.user:
            try:
                # Try to get the app label and model name from the user model
                app_label = obj.user._meta.app_label
                model_name = obj.user._meta.model_name
                url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.user.id])
                return format_html('<a href="{}">{}</a>', url, obj.user.email)
            except:
                # Fallback to just showing the email without a link
                return obj.user.email
        return "-"
    user_link.short_description = 'User'
    
    def status_badge(self, obj):
        status_colors = {
            'PENDING': 'bg-warning',
            'PROCESSING': 'bg-info',
            'IN_TRANSIT': 'bg-primary',
            'DELIVERED': 'bg-success',
            'CANCELLED': 'bg-danger'
        }
        color = status_colors.get(obj.status, 'bg-secondary')
        return format_html(
            '<span class="badge {}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def payment_status_badge(self, obj):
        status_colors = {
            'PENDING': 'bg-warning',
            'PAID': 'bg-success',
            'FAILED': 'bg-danger',
            'REFUNDED': 'bg-info'
        }
        color = status_colors.get(obj.payment_status, 'bg-secondary')
        return format_html(
            '<span class="badge {}">{} {}</span>',
            color,
            obj.get_payment_method_display(),
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'
    
    def total_cost_display(self, obj):
        return f"${obj.total_cost}"
    total_cost_display.short_description = 'Total Cost'
    
    def receipt_download(self, obj):
        if obj.receipt:
            return format_html(
                '<a href="{}" class="button" target="_blank">Download Receipt</a>',
                obj.receipt.url
            )
        return "-"
    receipt_download.short_description = 'Receipt'
    
    def mark_payment_as_paid(self, request, queryset):
        updated = queryset.update(
            payment_status=ShipmentRequest.PaymentStatus.PAID,
            payment_date=timezone.now()
        )
        self.message_user(
            request,
            f"Successfully marked {updated} shipments as paid",
            messages.SUCCESS
        )
    mark_payment_as_paid.short_description = "Mark payment as Paid"
    
    def mark_payment_as_failed(self, request, queryset):
        updated = queryset.update(
            payment_status=ShipmentRequest.PaymentStatus.FAILED,
            payment_date=timezone.now()
        )
        self.message_user(
            request,
            f"Successfully marked {updated} shipments as failed",
            messages.SUCCESS
        )
    mark_payment_as_failed.short_description = "Mark payment as Failed"


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Admin interface for support tickets"""
    list_display = [
        'ticket_number',
        'subject',
        'category',
        'status',
        'user_email',
        'assigned_to_email',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'category',
        'created_at',
        'resolved_at'
    ]
    
    search_fields = [
        'ticket_number',
        'subject',
        'message',
        'user__email',
        'assigned_to__email'
    ]
    
    readonly_fields = [
        'ticket_number',
        'created_at',
        'updated_at',
        'resolved_at',
        'comments_display'
    ]
    
    fieldsets = [
        ('Ticket Information', {
            'fields': (
                'ticket_number',
                'subject',
                'message',
                'category',
                'status'
            )
        }),
        ('User & Assignment', {
            'fields': (
                'user',
                'assigned_to',
                'shipment'
            )
        }),
        ('Dates', {
            'fields': (
                'created_at',
                'updated_at',
                'resolved_at'
            )
        }),
        ('Comments', {
            'fields': ('comments_display',)
        })
    ]
    
    actions = ['mark_as_in_progress', 'mark_as_resolved', 'mark_as_closed']
    
    def get_queryset(self, request):
        """Optimize queryset for admin listing"""
        return super().get_queryset(request).select_related('user', 'assigned_to')
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email if obj.user else '-'
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def assigned_to_email(self, obj):
        """Display assigned staff email"""
        return obj.assigned_to.email if obj.assigned_to else '-'
    assigned_to_email.short_description = 'Assigned To'
    assigned_to_email.admin_order_field = 'assigned_to__email'
    
    def comments_display(self, obj):
        """Display comments in a readable format"""
        if not obj.comments:
            return "No comments yet"
            
        html = ['<div style="max-height: 400px; overflow-y: auto;">']
        for comment in obj.comments:
            try:
                timestamp = timezone.datetime.fromisoformat(comment['timestamp'])
                formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                formatted_time = 'Invalid date'
            
            html.append(
                f'<p><strong>{comment["user"]}</strong> '
                f'({formatted_time}):<br>'
                f'{comment["comment"]}</p>'
            )
        
        html.append('</div>')
        return format_html(''.join(html))
    comments_display.short_description = 'Comments'
    
    def mark_as_in_progress(self, request, queryset):
        """Mark selected tickets as in progress"""
        updated = queryset.update(
            status=SupportTicket.Status.IN_PROGRESS,
            assigned_to=request.user
        )
        self.message_user(request, f"{updated} tickets marked as in progress and assigned to you.")
    mark_as_in_progress.short_description = "Mark as in progress"
    
    def mark_as_resolved(self, request, queryset):
        """Mark selected tickets as resolved"""
        updated = queryset.update(
            status=SupportTicket.Status.RESOLVED,
            resolved_at=timezone.now()
        )
        self.message_user(request, f"{updated} tickets marked as resolved.")
    mark_as_resolved.short_description = "Mark as resolved"
    
    def mark_as_closed(self, request, queryset):
        """Mark selected tickets as closed"""
        updated = queryset.update(status=SupportTicket.Status.CLOSED)
        self.message_user(request, f"{updated} tickets marked as closed.")
    mark_as_closed.short_description = "Mark as closed"
