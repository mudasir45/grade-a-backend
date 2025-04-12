from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import User

from .models import Buy4MeItem, Buy4MeRequest


class StaffAssignmentFilter(admin.SimpleListFilter):
    """Filter requests by whether they have a staff member assigned"""
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
    """Filter Buy4Me requests by driver status"""
    title = 'Driver'
    parameter_name = 'driver'
    
    def lookups(self, request, model_admin):
        # Get all active drivers
        drivers = User.objects.filter(
            driver_profile__is_active=True,
            user_type='DRIVER'
        ).values_list('id', 'email')
        return [('none', 'No driver')] + [(str(id), email) for id, email in drivers]
    
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(driver=None)
        if self.value():
            return queryset.filter(driver_id=self.value())
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    """Filter requests by date range"""
    title = 'Date Range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_year', 'This Year'),
        )
    
    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=today)
        
        if self.value() == 'yesterday':
            yesterday = today - timezone.timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        
        if self.value() == 'this_week':
            start_of_week = today - timezone.timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=start_of_week)
        
        if self.value() == 'last_week':
            start_of_this_week = today - timezone.timedelta(days=today.weekday())
            start_of_last_week = start_of_this_week - timezone.timedelta(days=7)
            end_of_last_week = start_of_this_week - timezone.timedelta(days=1)
            return queryset.filter(created_at__date__gte=start_of_last_week, created_at__date__lte=end_of_last_week)
        
        if self.value() == 'this_month':
            return queryset.filter(created_at__month=today.month, created_at__year=today.year)
        
        if self.value() == 'last_month':
            last_month = today.month - 1 if today.month > 1 else 12
            year = today.year if today.month > 1 else today.year - 1
            return queryset.filter(created_at__month=last_month, created_at__year=year)
        
        if self.value() == 'this_year':
            return queryset.filter(created_at__year=today.year)
        
        return queryset


class Buy4MeItemInline(admin.TabularInline):
    model = Buy4MeItem
    extra = 1
    classes = ('wide',)
    verbose_name = "Product Item"
    verbose_name_plural = "Product Items"
    fields = [
        'product_name', 'product_url', 'quantity',
        'unit_price', 'currency', 'total_price' 
    ]
    readonly_fields = ['total_price']
    
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'class': 'vTextField'})},
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 3})},
        models.URLField: {'widget': forms.URLInput(attrs={'class': 'vURLField'})},
        models.DecimalField: {'widget': forms.NumberInput(attrs={'step': '0.01'})},
        models.PositiveIntegerField: {'widget': forms.NumberInput(attrs={'min': '1'})},
    }
    
    def total_price(self, obj):
        if obj and obj.quantity and obj.unit_price:
            return f"{obj.currency} {obj.total_price:.2f}"
        return '-'
    total_price.short_description = 'Total'


class Buy4MeStatusFilter(admin.SimpleListFilter):
    """Filter Buy4Me requests by common status groups"""
    title = 'Status Group'
    parameter_name = 'status_group'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active (Not Completed)'),
            ('in_process', 'In Process'),
            ('delivery', 'In Delivery'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.exclude(status__in=['COMPLETED', 'CANCELLED'])
        
        if self.value() == 'in_process':
            return queryset.filter(status__in=['SUBMITTED', 'ORDER_PLACED'])
        
        if self.value() == 'delivery':
            return queryset.filter(status__in=['IN_TRANSIT', 'WAREHOUSE_ARRIVED', 'SHIPPED_TO_CUSTOMER'])
        
        if self.value() == 'completed':
            return queryset.filter(status='COMPLETED')
        
        if self.value() == 'cancelled':
            return queryset.filter(status='CANCELLED')
        
        return queryset


@admin.register(Buy4MeRequest)
class Buy4MeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'status_badge', 'payment_status_badge',
        'user_info', 'items_count',
        'total_cost_display', 'created_at_display', 'actions_column'
    ]
    list_filter = [
        Buy4MeStatusFilter, 'payment_status', DateRangeFilter,
        StaffAssignmentFilter, DriverFilter, 'user'
    ]
    search_fields = [
        'id', 'user__username', 'user__email', 'user__first_name', 'user__last_name',
        'staff__username', 'staff__email',
        'driver__username', 'driver__email', 'shipping_address'
    ]
    readonly_fields = [
        'id', 'total_cost', 'service_fee', 'service_fee_percentage_display',
        'created_at', 'updated_at', 'driver', 'cost_breakdown_display',
        'items_summary'
    ]
    actions = [
        'assign_to_me', 'unassign_staff', 'mark_as_order_placed',
        'mark_as_in_transit', 'mark_as_completed', 'mark_as_cancelled'
    ]
    save_on_top = True
    list_per_page = 25
    
    # Using tabs
    fieldsets = (
        ('Order Information', {
            'fields': (
                # Basic Info
                'id', 
                'created_at', 
                'updated_at',
                'status', 
                'payment_status',
                
                # Assignment
                'user',
                'staff',
                'driver',
                
                # Shipping
                'shipping_address', 
                'notes',
                
                # Financial Info
                'cost_breakdown_display',
                'service_fee_percentage_display', 
                'service_fee',
                'total_cost',
            ),
            'classes': ('wide',),
            'description': 'Complete information about this Buy4Me request'
        }),
    )
    
    inlines = [Buy4MeItemInline]
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            item_count=Count('items')
        )
        return queryset
    
    def items_count(self, obj):
        count = getattr(obj, 'item_count', obj.items.count())
        url = reverse('admin:buy4me_buy4meitem_changelist')
        return format_html(
            '<a href="{}?buy4me_request__id={}" class="button" style="background-color: #417690; padding: 5px 10px; color: white; border-radius: 4px; text-decoration: none;">{} items</a>',
            url, obj.id, count
        )
    items_count.short_description = 'Items'
    items_count.admin_order_field = 'item_count'
    
    def items_summary(self, obj):
        items = obj.items.all()
        if not items:
            return "No items yet"
        
        html = """
        <style>
            .items-summary {
                width: 100%;
                border-collapse: collapse;
            }
            .items-summary th, .items-summary td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            .items-summary th {
                background-color: #f5f5f5;
            }
            .items-summary tr:hover {
                background-color: #f9f9f9;
            }
            .items-summary .view-btn {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                border-radius: 4px;
            }
        </style>
        <table class="items-summary">
            <tr>
                <th>Product</th>
                <th>Quantity</th>
                <th>Unit Price</th>
                <th>Total</th>
                <th>Link</th>
            </tr>
        """
        
        for item in items:
            html += f"""
            <tr>
                <td>{item.product_name}</td>
                <td>{item.quantity}</td>
                <td>{item.currency} {item.unit_price}</td>
                <td><b>{item.currency} {item.total_price}</b></td>
                <td><a href="{item.product_url}" target="_blank" class="view-btn">View</a></td>
            </tr>
            """
        
        html += "</table>"
        return mark_safe(html)
    items_summary.short_description = 'Items Summary'
    
    def user_info(self, obj):
        if not obj.user:
            return "-"
        user_url = reverse('admin:accounts_user_change', args=[obj.user.id])
        name = f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        return format_html(
            '<div><a href="{}" style="font-weight: bold;">{}</a></div>'
            '<div style="color: #666;">{}</div>',
            user_url, name, obj.user.email
        )
    user_info.short_description = 'Customer'
    user_info.admin_order_field = 'user__username'
    
    def created_at_display(self, obj):
        return format_html(
            '<div>{}</div><div style="color: #666; font-size: 12px;">{} days ago</div>',
            obj.created_at.strftime('%Y-%m-%d %H:%M'),
            (timezone.now().date() - obj.created_at.date()).days
        )
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'
    
    def actions_column(self, obj):
        view_url = reverse('admin:buy4me_buy4merequest_change', args=[obj.id])
        
        # Status dependent actions
        action_buttons = ""
        if obj.status not in ['COMPLETED', 'CANCELLED']:
            if obj.status == 'DRAFT':
                action_buttons += self._action_button("Mark Submitted", "submit", obj.id, "info")
            elif obj.status == 'SUBMITTED':
                action_buttons += self._action_button("Order Placed", "order_placed", obj.id, "primary")
            elif obj.status == 'ORDER_PLACED':
                action_buttons += self._action_button("In Transit", "in_transit", obj.id, "warning")
            elif obj.status in ['IN_TRANSIT', 'WAREHOUSE_ARRIVED']:
                action_buttons += self._action_button("Complete", "complete", obj.id, "success")
        
        html = f"""
        <div style="display: flex; flex-direction: column; gap: 5px;">
            {action_buttons}
        </div>
        """
        return mark_safe(html)
    actions_column.short_description = 'Quick Actions'
    
    def _action_button(self, text, action, obj_id, color="primary"):
        colors = {
            "primary": "#007bff",
            "success": "#28a745",
            "info": "#17a2b8",
            "warning": "#ffc107",
            "danger": "#dc3545"
        }
        return f"""
        <a href="javascript:void(0);" 
           onclick="confirmAction('{action}', {obj_id})"
           style="background-color: {colors.get(color, '#6c757d')}; 
                  color: white; 
                  padding: 5px 10px; 
                  border-radius: 4px; 
                  text-decoration: none; 
                  font-size: 12px;
                  text-align: center;">
            {text}
        </a>
        """
    
    def payment_status_badge(self, obj):
        colors = {
            'PENDING': '#ffc107',  # Yellow
            'PAID': '#28a745',     # Green
            'COD': '#17a2b8',      # Blue
            'COD_PAID': '#0d6efd',  # Darker blue
            'REFUNDED': '#dc3545',  # Red
            'CANCELLED': '#6c757d'  # Gray
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(obj.payment_status, '#6c757d'),
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'
    
    def service_fee_percentage_display(self, obj):
        return f"{obj.service_fee_percentage}%" 
    service_fee_percentage_display.short_description = 'Service Fee %'
    
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
            return format_html(
                '<a href="../../../auth/user/{}/change/">{}</a>',
                obj.staff.id,
                obj.staff.email
            )
        return "-"
    staff_link.short_description = 'Staff'
    
    def driver_link(self, obj):
        if obj.driver:
            return format_html(
                '<a href="../../../auth/user/{}/change/">{}</a>',
                obj.driver.id,
                obj.driver.email
            )
        return "-"
    driver_link.short_description = 'Driver'
    
    def assign_to_me(self, request, queryset):
        """Assign selected requests to the current user if they have staff status"""
        if not request.user.is_staff:
            self.message_user(
                request, 
                "You cannot assign requests to yourself because you don't have staff status.",
                messages.ERROR
            )
            return
            
        updated = queryset.update(staff=request.user)
        self.message_user(request, f"{updated} requests assigned to you.")
    assign_to_me.short_description = "Assign selected requests to me"
    
    def unassign_staff(self, request, queryset):
        updated = queryset.update(staff=None)
        self.message_user(request, f"{updated} requests unassigned from staff.")
    unassign_staff.short_description = "Unassign staff from selected requests"
    
    def unassign_driver(self, request, queryset):
        updated = queryset.update(driver=None)
        self.message_user(request, f"{updated} requests unassigned from driver.")
    unassign_driver.short_description = "Unassign driver from selected requests"
    
    def mark_as_order_placed(self, request, queryset):
        """Mark selected requests as ORDER_PLACED"""
        updated = queryset.filter(status='SUBMITTED').update(status='ORDER_PLACED')
        self.message_user(request, f"{updated} requests marked as Order Placed.")
    mark_as_order_placed.short_description = "Mark selected as Order Placed"
    
    def mark_as_in_transit(self, request, queryset):
        """Mark selected requests as IN_TRANSIT"""
        updated = queryset.filter(status='ORDER_PLACED').update(status='IN_TRANSIT')
        self.message_user(request, f"{updated} requests marked as In Transit.")
    mark_as_in_transit.short_description = "Mark selected as In Transit"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected requests as COMPLETED"""
        updated = queryset.filter(status__in=['IN_TRANSIT', 'WAREHOUSE_ARRIVED', 'SHIPPED_TO_CUSTOMER']).update(status='COMPLETED')
        self.message_user(request, f"{updated} requests marked as Completed.")
    mark_as_completed.short_description = "Mark selected as Completed"
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected requests as CANCELLED"""
        updated = queryset.exclude(status__in=['COMPLETED', 'CANCELLED']).update(status='CANCELLED')
        self.message_user(request, f"{updated} requests marked as Cancelled.")
    mark_as_cancelled.short_description = "Mark selected as Cancelled"
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': '#6c757d',      # Gray
            'SUBMITTED': '#17a2b8',  # Blue
            'ORDER_PLACED': '#0d6efd', # Purple
            'IN_TRANSIT': '#ffc107',  # Yellow
            'WAREHOUSE_ARRIVED': '#fd7e14',  # Orange
            'SHIPPED_TO_CUSTOMER': '#0dcaf0',  # Light blue
            'COMPLETED': '#28a745',  # Green
            'CANCELLED': '#dc3545'   # Red
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_cost_display(self, obj):
        # Get items total
        items_total = obj.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        
        # Build detailed breakdown
        breakdown = f"""
            Items Total: ${items_total:.2f}<br>
            <b>Service Fee: ${obj.service_fee:.2f}</b><br>
            <b>Total: ${obj.total_cost:.2f}</b>
        """
        
        return format_html(
            '<span title="{}" data-toggle="tooltip" data-html="true"><b>${}</b></span>',
            breakdown,
            obj.total_cost
        )
    total_cost_display.short_description = 'Total'
    
    def cost_breakdown_display(self, obj):
        """Display a formatted cost breakdown table"""
        # Get items total
        items_total = obj.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        
        # Build HTML table
        html = """
        <style>
            .cost-table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
                font-family: Arial, sans-serif;
                border: 1px solid #e0e0e0;
            }
            .cost-table th, .cost-table td {
                padding: 10px 12px;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
            }
            .cost-table th {
                background-color: #f5f5f5;
                font-weight: bold;
                color: #333;
                border-bottom: 2px solid #ddd;
            }
            .cost-table td:last-child {
                text-align: right;
                font-family: monospace;
                font-size: 14px;
            }
            .cost-table .subtotal {
                background-color: #f9f9f9;
                font-weight: bold;
            }
            .cost-table .total {
                background-color: #1a237e;
                color: white;
                font-weight: bold;
            }
            .cost-table .total td {
                padding: 12px;
            }
            .cost-table tr:hover {
                background-color: #f8f8f8;
            }
            .cost-table .total:hover {
                background-color: #1a237e;
            }
        </style>
        <table class="cost-table">
            <tr>
                <th style="width: 70%%">Cost Component</th>
                <th style="width: 30%%">Amount</th>
            </tr>
            <tr>
                <td>Items Total</td>
                <td>$%.2f</td>
            </tr>
            <tr>
                <td>Service Fee</td>
                <td>$%.2f</td>
            </tr>
            <tr class="total">
                <td>Total Cost</td>
                <td>$%.2f</td>
            </tr>
        </table>
        """
        
        # Format the HTML with the values
        html = html % (items_total, obj.service_fee, obj.total_cost)
        
        return mark_safe(html)
    cost_breakdown_display.short_description = 'Cost Breakdown'
    
    class Media:
        js = ('js/buy4me_admin.js',)
        css = {
            'all': ('css/buy4me_admin.css',)
        }


@admin.register(Buy4MeItem)
class Buy4MeItemAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'request_link', 'product_name', 
        'quantity', 'unit_price_display',
        'total_price_display', 'view_product'
    ]
    list_filter = ['created_at', 'buy4me_request__status']
    search_fields = [
        'product_name', 'product_url', 'buy4me_request__id',
        'buy4me_request__user__username', 'buy4me_request__user__email'
    ]
    readonly_fields = ['created_at', 'updated_at', 'product_preview']
    fieldsets = (
        ('Product Information', {
            'fields': (
                'product_name', 'product_url', 'product_preview',
                ('quantity', 'unit_price', 'currency'),
                'color', 'size', 'notes'
            )
        }),
        ('Shipping & Fees', {
            'fields': ('store_to_warehouse_delivery_charge',)
        }),
        ('Request Information', {
            'fields': ('buy4me_request', 'created_at', 'updated_at')
        }),
    )
    
    def product_preview(self, obj):
        if obj.product_url:
            return format_html(
                '<a href="{}" target="_blank" class="button" style="background-color: #28a745; padding: 7px 15px; color: white; border-radius: 4px; text-decoration: none; display: inline-block; margin-top: 10px;">View Product Online</a>',
                obj.product_url
            )
        return 'No URL provided'
    product_preview.short_description = 'Product Preview'
    
    def view_product(self, obj):
        if obj.product_url:
            return format_html(
                '<a href="{}" target="_blank" class="button" style="background-color: #28a745; padding: 5px 10px; color: white; border-radius: 4px; text-decoration: none;">View</a>',
                obj.product_url
            )
        return '-'
    view_product.short_description = 'View'
    
    def request_link(self, obj):
        url = reverse('admin:buy4me_buy4merequest_change', args=[obj.buy4me_request.id])
        status_colors = {
            'DRAFT': '#6c757d',
            'SUBMITTED': '#17a2b8',
            'ORDER_PLACED': '#0d6efd',
            'IN_TRANSIT': '#ffc107',
            'WAREHOUSE_ARRIVED': '#fd7e14',
            'SHIPPED_TO_CUSTOMER': '#0dcaf0',
            'COMPLETED': '#28a745',
            'CANCELLED': '#dc3545'
        }
        status_color = status_colors.get(obj.buy4me_request.status, '#6c757d')
        
        return format_html(
            '<div><a href="{}" style="font-weight: bold;">{}</a></div>'
            '<div><span style="background-color: {}; color: white; padding: 2px 5px; border-radius: 10px; font-size: 10px;">{}</span></div>',
            url,
            obj.buy4me_request.id,
            status_color,
            obj.buy4me_request.get_status_display()
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
