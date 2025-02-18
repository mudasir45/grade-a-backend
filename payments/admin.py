from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Invoice, Payment, Refund

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['status_badge', 'amount_display', 'created_at']
    fields = ['payment_method', 'status_badge', 'amount_display', 'transaction_id', 'created_at']
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'COMPLETED': 'success',
            'FAILED': 'danger',
            'REFUNDED': 'info'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def amount_display(self, obj):
        return format_html('<b>${}</b>', obj.amount)
    amount_display.short_description = 'Amount'

class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    readonly_fields = ['status_badge', 'amount_display', 'processed_by', 'created_at']
    fields = ['status_badge', 'amount_display', 'reason', 'processed_by', 'created_at']
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'APPROVED': 'info',
            'COMPLETED': 'success',
            'REJECTED': 'danger'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def amount_display(self, obj):
        return format_html('<b>${}</b>', obj.amount)
    amount_display.short_description = 'Amount'

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'reference_link', 'status_badge',
        'total_display', 'due_date_status', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'due_date']
    search_fields = [
        'id', 'user__email', 'user__username',
        'shipment__tracking_number', 'buy4me_request__id'
    ]
    readonly_fields = ['total', 'created_at', 'updated_at']
    inlines = [PaymentInline]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user', 'status', 'due_date',
                'created_at', 'updated_at'
            )
        }),
        ('Related Records', {
            'fields': ('shipment', 'buy4me_request')
        }),
        ('Financial Details', {
            'fields': (
                'subtotal', 'tax', 'total'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def reference_link(self, obj):
        if obj.shipment:
            url = reverse('admin:shipments_shipmentrequest_change', args=[obj.shipment.id])
            return format_html(
                '<a href="{}">Shipment #{}</a>',
                url,
                obj.shipment.tracking_number
            )
        elif obj.buy4me_request:
            url = reverse('admin:buy4me_buy4merequest_change', args=[obj.buy4me_request.id])
            return format_html(
                '<a href="{}">Buy4Me #{}</a>',
                url,
                obj.buy4me_request.id
            )
        return '-'
    reference_link.short_description = 'Reference'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'secondary',
            'PENDING': 'warning',
            'PAID': 'success',
            'OVERDUE': 'danger',
            'CANCELLED': 'danger',
            'REFUNDED': 'info'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_display(self, obj):
        return format_html('<b>${}</b>', obj.total)
    total_display.short_description = 'Total'
    
    def due_date_status(self, obj):
        if obj.status in ['PAID', 'CANCELLED', 'REFUNDED']:
            return obj.due_date
        
        if obj.due_date < timezone.now().date():
            return format_html(
                '<span class="badge badge-danger">Overdue</span><br>{}'.format(
                    obj.due_date
                )
            )
        return format_html(
            '<span class="badge badge-success">Due</span><br>{}'.format(
                obj.due_date
            )
        )
    due_date_status.short_description = 'Due Date'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'invoice_link', 'payment_method_badge',
        'status_badge', 'amount_display', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = [
        'id', 'invoice__id', 'transaction_id',
        'invoice__user__email'
    ]
    readonly_fields = [
        'transaction_id', 'payment_details',
        'created_at', 'updated_at'
    ]
    inlines = [RefundInline]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'invoice', 'payment_method', 'status',
                'created_at', 'updated_at'
            )
        }),
        ('Payment Details', {
            'fields': (
                'amount', 'transaction_id',
                'payment_details'
            )
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:payments_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.id)
    invoice_link.short_description = 'Invoice'
    
    def payment_method_badge(self, obj):
        colors = {
            'STRIPE': 'primary',
            'PAYPAL': 'info',
            'BANK_TRANSFER': 'warning',
            'CASH': 'success'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.payment_method, 'secondary'),
            obj.get_payment_method_display()
        )
    payment_method_badge.short_description = 'Method'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'COMPLETED': 'success',
            'FAILED': 'danger',
            'REFUNDED': 'info'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def amount_display(self, obj):
        return format_html('<b>${}</b>', obj.amount)
    amount_display.short_description = 'Amount'

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'payment_link', 'status_badge',
        'amount_display', 'processed_by_link', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'id', 'payment__invoice__id',
        'payment__transaction_id', 'reason'
    ]
    readonly_fields = [
        'processed_by', 'refund_transaction_id',
        'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'payment', 'status', 'amount',
                'processed_by', 'created_at', 'updated_at'
            )
        }),
        ('Refund Details', {
            'fields': (
                'reason', 'refund_transaction_id'
            )
        }),
    )
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.id)
    payment_link.short_description = 'Payment'
    
    def processed_by_link(self, obj):
        if obj.processed_by:
            url = reverse('admin:accounts_user_change', args=[obj.processed_by.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.processed_by.get_full_name() or obj.processed_by.email
            )
        return '-'
    processed_by_link.short_description = 'Processed By'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'APPROVED': 'info',
            'COMPLETED': 'success',
            'REJECTED': 'danger'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'secondary'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def amount_display(self, obj):
        return format_html('<b>${}</b>', obj.amount)
    amount_display.short_description = 'Amount'
