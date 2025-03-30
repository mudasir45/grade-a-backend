from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import City, DriverProfile, User

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


class CityFilter(admin.SimpleListFilter):
    """Filter Buy4Me requests by city"""
    title = 'City'
    parameter_name = 'city'
    
    def lookups(self, request, model_admin):
        # Get all active cities
        cities = City.objects.filter(is_active=True).values_list('id', 'name')
        return [('none', 'No city')] + [(str(id), name) for id, name in cities]
    
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(city=None)
        if self.value():
            return queryset.filter(city_id=self.value())
        return queryset


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
        'id', 'status_badge', 
        'user', 'staff_link', 'driver_link', 'city_link',
        'total_cost_display', 'delivery_charge_display', 'created_at'
    ]
    list_filter = ['status', 'created_at', StaffAssignmentFilter, DriverFilter, CityFilter]
    search_fields = [
        'id', 'user__username', 'user__email',
        'staff__username', 'staff__email',
        'driver__username', 'driver__email',
        'city__name'
    ]
    inlines = [Buy4MeItemInline]
    readonly_fields = ['total_cost', 'created_at', 'updated_at', 'driver', 'city_delivery_charge', 'cost_breakdown_display']
    actions = ['assign_to_driver', 'unassign_driver', 'assign_to_me', 'unassign_staff', 'assign_to_city']
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'user',
                'staff',
                'driver',
                'city',
            ),
            'classes': ('wide',),
            'description': 'Manage user, staff, driver, and city assignments'
        }),
        ('Status Information', {
            'fields': (
                'status', 'created_at', 'updated_at'
            )
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'notes')
        }),
        ('Cost Information', {
            'fields': (
                'cost_breakdown_display',
                'city_delivery_charge',
                'total_cost',
            ),
            'description': 'Cost breakdown including delivery charge and total'
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
    
    def city_link(self, obj):
        if obj.city:
            url = reverse('admin:accounts_city_change', args=[obj.city.id])
            return format_html('<a href="{}">{}</a>', url, obj.city.name)
        return "-"
    city_link.short_description = 'City'
    
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
    
    def assign_to_driver(self, request, queryset):
        """Action to assign selected requests to a driver"""
        self.message_user(
            request,
            "Drivers should be assigned automatically through city selection. "
            "Please use the 'Assign to City' action instead.",
            messages.WARNING
        )
        return None
    
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
        # Get items total
        items_total = obj.items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_price'))
        )['total'] or 0
        
        # Build detailed breakdown
        breakdown = f"""
            Items Total: ${items_total:.2f}<br>
            <b>Delivery Charge: ${obj.city_delivery_charge:.2f}</b><br>
            <b>Total: ${obj.total_cost:.2f}</b>
        """
        
        return format_html(
            '<span title="{}" data-toggle="tooltip" data-html="true"><b>${}</b></span>',
            breakdown,
            obj.total_cost
        )
    total_cost_display.short_description = 'Total Cost'
    
    def delivery_charge_display(self, obj):
        return format_html('<b>${}</b>', obj.city_delivery_charge)
    delivery_charge_display.short_description = 'Delivery Charge'
    
    def assign_to_city(self, request, queryset):
        """Action to assign selected requests to a city"""
        if request.POST.get('city_id'):
            city_id = request.POST.get('city_id')
            try:
                city = City.objects.get(id=city_id, is_active=True)
                updated = queryset.update(
                    city=city,
                    city_delivery_charge=city.delivery_charge
                )
                
                # For each updated request, try to assign a driver
                for buy4me_request in queryset:
                    # Get active drivers assigned to this city
                    driver_profiles = DriverProfile.objects.filter(
                        cities=city,
                        is_active=True
                    )
                    driver_profile = driver_profiles.first()
                    if driver_profile:
                        buy4me_request.driver = driver_profile.user
                        buy4me_request.save(update_fields=['driver'])
                
                self.message_user(
                    request,
                    f"{updated} requests assigned to city {city.name}",
                    messages.SUCCESS
                )
                return None
            except City.DoesNotExist:
                self.message_user(
                    request,
                    "Selected city not found or is not active",
                    messages.ERROR
                )
                return None
        
        # Get all active cities
        cities = City.objects.filter(is_active=True).values_list('id', 'name')
        
        if not cities:
            self.message_user(
                request,
                "No active cities found in the system.",
                messages.ERROR
            )
            return None
        
        # Create the HTML for the city selection form
        city_options = "\n".join(
            f'<option value="{id}">{name}</option>'
            for id, name in cities
        )
        
        # Return a custom admin action page
        return format_html("""
            <form action="" method="post">
                <input type="hidden" name="action" value="assign_to_city" />
                <input type="hidden" name="_selected_action" value="{}" />
                {}
                <p>Select a city to assign the selected requests to:</p>
                <select name="city_id">
                    {}
                </select>
                <input type="submit" value="Assign City" />
            </form>
        """,
        ",".join(str(obj.pk) for obj in queryset),
        request.POST.get('csrfmiddlewaretoken', ''),
        city_options
        )
    
    assign_to_city.short_description = "Assign selected requests to city"

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
                <td>Delivery Charge</td>
                <td>$%.2f</td>
            </tr>
            <tr class="total">
                <td>Total Cost</td>
                <td>$%.2f</td>
            </tr>
        </table>
        """
        
        # Format the HTML with the values
        html = html % (items_total, obj.city_delivery_charge, obj.total_cost)
        
        return mark_safe(html)
    cost_breakdown_display.short_description = 'Cost Breakdown'

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
