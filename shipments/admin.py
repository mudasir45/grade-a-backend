from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html

from accounts.models import User

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
        'user_link', 'staff_link', 'sender_name', 'recipient_name',
        'service_type', 'total_cost_display', 'receipt_download', 'id', 'created_at'
    ]
    list_filter = [
        'status', 'payment_method', 'payment_status',
        'service_type', 'created_at', 'staff',
        StaffAssignmentFilter
    ]
    search_fields = [
        'tracking_number', 'sender_name', 'recipient_name', 
        'current_location', 'user__email', 'staff__email',
        'transaction_id'
    ]
    readonly_fields = [
        'tracking_number', 'tracking_history',
        'created_at', 'updated_at', 'receipt_download',
        'cod_amount', 'total_cost'
    ]
    
    # Base actions that are always available
    actions = [
        'assign_to_me',
        'unassign_staff',
        'mark_payment_as_paid',
        'mark_payment_as_failed'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'staff')
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
    
    def get_actions(self, request):
        """
        Dynamically add status update actions based on ShipmentStatusLocation entries
        """
        actions = super().get_actions(request)
        
        # Get all active status locations
        status_locations = ShipmentStatusLocation.objects.filter(is_active=True)
        
        # Group by status type
        status_groups = {}
        for location in status_locations:
            if location.status_type not in status_groups:
                status_groups[location.status_type] = []
            status_groups[location.status_type].append(location)
        
        # Add dynamic actions for each status location
        for status_type, locations in status_groups.items():
            for location in locations:
                action_name = f"mark_as_{status_type.lower()}_{location.id}"
                action_display_name = f"Mark as {location.get_status_type_display()} - {location.location_name}"
                
                # Create a closure to capture the current location
                def make_action(loc):
                    def action(modeladmin, request, queryset):
                        # Get the corresponding ShipmentRequest.Status
                        status_mapping = ShipmentStatusLocation.get_status_mapping()
                        shipment_status = status_mapping.get(loc.status_type)
                        
                        for shipment in queryset:
                            shipment.update_tracking(
                                shipment_status,
                                loc.location_name,
                                loc.description
                            )
                        
                        count = queryset.count()
                        modeladmin.message_user(
                            request,
                            f"Successfully updated {count} shipments to {loc.get_status_type_display()} at {loc.location_name}",
                            messages.SUCCESS
                        )
                    
                    # Set a unique name for the function
                    action.__name__ = action_name
                    action.short_description = action_display_name
                    return action
                
                actions[action_name] = (make_action(location), action_name, action_display_name)
        
        return actions
    
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
    
    def staff_link(self, obj):
        if obj.staff:
            try:
                # Try to get the app label and model name from the staff user model
                app_label = obj.staff._meta.app_label
                model_name = obj.staff._meta.model_name
                url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.staff.id])
                return format_html('<a href="{}">{}</a>', url, obj.staff.email)
            except:
                # Fallback to just showing the email without a link
                return obj.staff.email
        return "-"
    staff_link.short_description = 'Staff'
    
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
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Override to filter the staff dropdown to only show staff users"""
        if db_field.name == "staff":
            User = get_user_model()
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Admin interface for support tickets"""
    list_display = [
        'ticket_number',
        'subject',
        'category',
        'status_badge',
        'priority',
        'user_link',
        'assigned_to_link',
        'created_at',
        'response_time_display'
    ]
    
    list_filter = [
        'status',
        'category',
        'priority',
        'created_at',
        'resolved_at',
        ('assigned_to', admin.EmptyFieldListFilter),
    ]
    
    search_fields = [
        'ticket_number',
        'subject',
        'message',
        'user__email',
        'user__first_name',
        'user__last_name',
        'assigned_to__email'
    ]
    
    readonly_fields = [
        'ticket_number',
        'created_at',
        'updated_at',
        'resolved_at',
        'response_time',
        'resolution_time',
        'communication_history_display'
    ]
    
    fieldsets = [
        ('Ticket Information', {
            'fields': (
                'ticket_number',
                'subject',
                'message',
                'category',
                'priority'
            )
        }),
        ('Status & Assignment', {
            'fields': (
                'status',
                'assigned_to',
                'shipment'
            )
        }),
        ('Timing Information', {
            'fields': (
                'created_at',
                'updated_at',
                'resolved_at',
                'response_time',
                'resolution_time'
            )
        }),
        ('Communication History', {
            'fields': ('communication_history_display',)
        })
    ]
    
    actions = ['mark_as_in_progress', 'mark_as_resolved', 'mark_as_closed']
    
    def get_queryset(self, request):
        """Optimize queryset for admin listing"""
        return super().get_queryset(request).select_related(
            'user',
            'assigned_to',
            'shipment'
        )
    
    def status_badge(self, obj):
        """Display status with color-coded badge"""
        colors = {
            'OPEN': 'red',
            'IN_PROGRESS': 'orange',
            'RESOLVED': 'green',
            'CLOSED': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def user_link(self, obj):
        """Display link to user"""
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__email'
    
    def assigned_to_link(self, obj):
        """Display link to assigned staff member"""
        if obj.assigned_to:
            url = reverse('admin:accounts_user_change', args=[obj.assigned_to.id])
            return format_html('<a href="{}">{}</a>', url, obj.assigned_to.email)
        return '-'
    assigned_to_link.short_description = 'Assigned To'
    assigned_to_link.admin_order_field = 'assigned_to__email'
    
    def response_time_display(self, obj):
        """Display response time in a human-readable format"""
        if obj.response_time:
            hours = obj.response_time.total_seconds() / 3600
            if hours < 24:
                return f"{hours:.1f} hours"
            days = hours / 24
            return f"{days:.1f} days"
        return '-'
    response_time_display.short_description = 'Response Time'
    response_time_display.admin_order_field = 'response_time'
    
    def communication_history_display(self, obj):
        """Display communication history in a readable format"""
        if not obj.communication_history:
            return "No communication history"
            
        html = ['<div style="max-height: 400px; overflow-y: auto;">']
        for entry in obj.communication_history:
            timestamp = parse_datetime(entry['timestamp'])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            if entry['type'] == 'comment':
                html.append(
                    f'<p><strong>{entry["user"]}</strong> '
                    f'({formatted_time}):<br>'
                    f'{entry["comment"]}</p>'
                )
            elif entry['type'] == 'status_change':
                html.append(
                    f'<p><em>Status changed from {entry["from_status"]} to '
                    f'{entry["to_status"]} by {entry["by_user"]} '
                    f'({formatted_time})</em></p>'
                )
        
        html.append('</div>')
        return format_html(''.join(html))
    communication_history_display.short_description = 'Communication History'
    
    def mark_as_in_progress(self, request, queryset):
        """Mark selected tickets as in progress"""
        updated = queryset.update(
            status=SupportTicket.Status.IN_PROGRESS,
            assigned_to=request.user
        )
        self.message_user(
            request,
            f"{updated} tickets marked as in progress and assigned to you."
        )
    mark_as_in_progress.short_description = "Mark selected tickets as in progress"
    
    def mark_as_resolved(self, request, queryset):
        """Mark selected tickets as resolved"""
        updated = queryset.update(
            status=SupportTicket.Status.RESOLVED,
            resolved_at=timezone.now()
        )
        self.message_user(
            request,
            f"{updated} tickets marked as resolved."
        )
    mark_as_resolved.short_description = "Mark selected tickets as resolved"
    
    def mark_as_closed(self, request, queryset):
        """Mark selected tickets as closed"""
        updated = queryset.update(status=SupportTicket.Status.CLOSED)
        self.message_user(request, f"{updated} tickets marked as closed.")
    mark_as_closed.short_description = "Mark selected tickets as closed"
