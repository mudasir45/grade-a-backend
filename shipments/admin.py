from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import ShipmentRequest


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


@admin.register(ShipmentRequest)
class ShipmentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_number', 'status_badge', 'user_link', 'staff_link',
        'sender_name', 'recipient_name', 'service_type',
        'total_cost_display', 'receipt_download', 'created_at'
    ]
    list_filter = ['status', 'service_type', 'created_at', 'staff', StaffAssignmentFilter]
    search_fields = [
        'tracking_number', 'sender_name', 'recipient_name', 
        'current_location', 'user__email', 'staff__email'
    ]
    readonly_fields = [
        'tracking_number', 'tracking_history',
        'created_at', 'updated_at', 'receipt_download'
    ]
    
    actions = [
        'mark_as_processing',
        'mark_as_picked_up',
        'mark_as_in_transit',
        'mark_as_out_for_delivery',
        'mark_as_delivered',
        'mark_as_cancelled',
        'assign_to_me',
        'unassign_staff'
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
                'total_additional_charges', 'total_cost'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
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
    
    def mark_as_processing(self, request, queryset):
        self._update_status(request, queryset, 'PROCESSING', 'Processing')
    mark_as_processing.short_description = "Mark as Processing"
    
    def mark_as_picked_up(self, request, queryset):
        for shipment in queryset:
            shipment.update_tracking(
                'PROCESSING',
                'Pickup Location',
                'Package picked up from sender'
            )
        count = queryset.count()
        self.message_user(
            request,
            f"Successfully updated {count} shipments",
            messages.SUCCESS
        )
    mark_as_picked_up.short_description = "Mark as Picked Up"
    
    def mark_as_in_transit(self, request, queryset):
        self._update_status(request, queryset, 'IN_TRANSIT', 'In Transit')
    mark_as_in_transit.short_description = "Mark as In Transit"
    
    def mark_as_out_for_delivery(self, request, queryset):
        for shipment in queryset:
            shipment.update_tracking(
                'IN_TRANSIT',
                'Destination City',
                'Out for delivery'
            )
        count = queryset.count()
        self.message_user(
            request,
            f"Successfully updated {count} shipments",
            messages.SUCCESS
        )
    mark_as_out_for_delivery.short_description = "Mark as Out for Delivery"
    
    def mark_as_delivered(self, request, queryset):
        self._update_status(request, queryset, 'DELIVERED', 'Delivered')
    mark_as_delivered.short_description = "Mark as Delivered"
    
    def mark_as_cancelled(self, request, queryset):
        self._update_status(request, queryset, 'CANCELLED', 'Cancelled')
    mark_as_cancelled.short_description = "Mark as Cancelled"
    
    def _update_status(self, request, queryset, status, location):
        for shipment in queryset:
            shipment.update_tracking(status, location)
        count = queryset.count()
        self.message_user(
            request,
            f"Successfully updated {count} shipments",
            messages.SUCCESS
        )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Override to filter the staff dropdown to only show staff users"""
        if db_field.name == "staff":
            User = get_user_model()
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
