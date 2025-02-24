from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from .models import ShipmentRequest, ShipmentTracking

class ShipmentTrackingInline(admin.TabularInline):
    model = ShipmentTracking
    extra = 0
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']

@admin.register(ShipmentRequest)
class ShipmentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_number', 'status_badge', 'current_location',
        'sender_name', 'recipient_name', 'service_type',
        'total_cost_display', 'receipt_download', 'created_at'
    ]
    list_filter = ['status', 'service_type', 'created_at']
    search_fields = [
        'tracking_number', 'sender_name', 'recipient_name',
        'current_location'
    ]
    readonly_fields = [
        'tracking_number', 'tracking_history',
        'created_at', 'updated_at', 'receipt_download'
    ]
    inlines = [ShipmentTrackingInline]
    
    actions = [
        'mark_as_processing',
        'mark_as_picked_up',
        'mark_as_in_transit',
        'mark_as_out_for_delivery',
        'mark_as_delivered',
        'mark_as_cancelled'
    ]
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'PROCESSING': 'info',
            'IN_TRANSIT': 'primary',
            'DELIVERED': 'success',
            'CANCELLED': 'danger'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def total_cost_display(self, obj):
        return format_html('<b>${}</b>', obj.total_cost)
    total_cost_display.short_description = 'Total Cost'

    def receipt_download(self, obj):
        if obj.receipt:
            return format_html(
                '<a class="button" href="{}" target="_blank">Download Receipt</a>',
                obj.receipt.url
            )
        return "No receipt available"
    receipt_download.short_description = "Receipt"

    def mark_as_processing(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.PROCESSING,
            'Warehouse',
            'Package received at processing facility'
        )
    mark_as_processing.short_description = "Mark selected shipments as Processing"

    def mark_as_picked_up(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.IN_TRANSIT,
            'Origin Facility',
            'Package picked up by courier'
        )
    mark_as_picked_up.short_description = "Mark selected shipments as Picked Up"

    def mark_as_in_transit(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.IN_TRANSIT,
            'Transit Hub',
            'Package in transit to destination'
        )
    mark_as_in_transit.short_description = "Mark selected shipments as In Transit"

    def mark_as_out_for_delivery(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.IN_TRANSIT,
            'Local Delivery Facility',
            'Package out for delivery'
        )
    mark_as_out_for_delivery.short_description = "Mark selected shipments as Out for Delivery"

    def mark_as_delivered(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.DELIVERED,
            'Destination',
            'Package delivered successfully'
        )
    mark_as_delivered.short_description = "Mark selected shipments as Delivered"

    def mark_as_cancelled(self, request, queryset):
        self._update_status(
            request, queryset,
            ShipmentRequest.Status.CANCELLED,
            'N/A',
            'Shipment cancelled'
        )
    mark_as_cancelled.short_description = "Mark selected shipments as Cancelled"

    def _update_status(self, request, queryset, status, location, description):
        """Helper method to update status and tracking history"""
        count = 0
        for shipment in queryset:
            try:
                shipment.update_tracking(status, location, description)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error updating shipment {shipment.tracking_number}: {str(e)}",
                    messages.ERROR
                )
        
        self.message_user(
            request,
            f"Successfully updated {count} shipments",
            messages.SUCCESS
        )

    fieldsets = (
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

@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = [
        'shipment_link', 'status', 'location', 
        'timestamp'
    ]
    list_filter = ['status', 'timestamp']
    search_fields = [
        'shipment__tracking_number', 'location', 
        'status', 'description'
    ]
    readonly_fields = ['timestamp']
    
    def shipment_link(self, obj):
        url = f"../shipmentrequest/{obj.shipment.id}"
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.shipment.tracking_number
        )
    shipment_link.short_description = 'Shipment'
