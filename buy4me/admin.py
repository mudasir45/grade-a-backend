from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from accounts.models import DriverProfile, User

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
        'id', 'user', 'staff_link', 'driver_link', 'status_badge',
        'total_cost_display', 'created_at'
    ]
    list_filter = ['status', 'created_at', StaffAssignmentFilter, DriverFilter]
    search_fields = [
        'id', 'user__username', 'user__email',
        'staff__username', 'staff__email',
        'driver__username', 'driver__email'
    ]
    inlines = [Buy4MeItemInline]
    readonly_fields = ['total_cost', 'created_at', 'updated_at']
    actions = ['assign_to_driver', 'unassign_driver', 'assign_to_me', 'unassign_staff']
    
    fieldsets = (
        ('Assignment Information', {
            'fields': (
                'user',
                'staff',
                'driver'
            ),
            'classes': ('wide',),
            'description': 'Manage user, staff, and driver assignments'
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
            'fields': ('total_cost',)
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
                    f"{updated} requests assigned to driver {driver.email}",
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
                <p>Select a driver to assign the selected requests to:</p>
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
    
    assign_to_driver.short_description = "Assign selected requests to driver"
    
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
