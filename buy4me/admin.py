from django.contrib import admin
from django.utils.html import format_html
from .models import Buy4MeRequest, Buy4MeItem

class Buy4MeItemInline(admin.TabularInline):
    model = Buy4MeItem
    extra = 0
    readonly_fields = ['total_price_display']
    fields = [
        'product_name', 'product_url', 'quantity',
        'unit_price', 'currency', 'total_price_display'
    ]

    def total_price_display(self, obj):
        if obj.total_price:
            return format_html('<b>{} {}</b>', obj.currency, obj.total_price)
        return '-'
    total_price_display.short_description = 'Total Price'

@admin.register(Buy4MeRequest)
class Buy4MeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'status_badge',
        'total_cost_display', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__username', 'user__email']
    inlines = [Buy4MeItemInline]
    readonly_fields = ['total_cost', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user', 'status', 'created_at', 
                'updated_at'
            )
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'notes')
        }),
        ('Cost Information', {
            'fields': ('total_cost',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'secondary',
            'SUBMITTED': 'info',
            'ORDER_PLACED': 'primary',
            'IN_TRANSIT': 'warning',
            'WAREHOUSE_ARRIVED': 'info',
            'SHIPPED_TO_CUSTOMER': 'primary',
            'COMPLETED': 'success'
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

@admin.register(Buy4MeItem)
class Buy4MeItemAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'request_link', 'product_name',
        'quantity', 'unit_price_display',
        'total_price_display'
    ]
    list_filter = ['created_at']
    search_fields = [
        'product_name', 'buy4me_request__id',
        'buy4me_request__user__username'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    def request_link(self, obj):
        url = f"../buy4merequest/{obj.buy4me_request.id}"
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.buy4me_request.id
        )
    request_link.short_description = 'Request'
    
    def unit_price_display(self, obj):
        return format_html(
            '<b>{} {}</b>',
            obj.currency,
            obj.unit_price
        )
    unit_price_display.short_description = 'Unit Price'
    
    def total_price_display(self, obj):
        return format_html(
            '<b>{} {}</b>',
            obj.currency,
            obj.total_price
        )
    total_price_display.short_description = 'Total Price'
