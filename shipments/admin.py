from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import ShipmentRequest, ShipmentStatusLocation


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
