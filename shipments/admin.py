import datetime
import uuid
from decimal import Decimal

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from accounts.models import City, DriverProfile, User
from shipping_rates.models import AdditionalCharge, Extras, ShippingZone

from .models import (ShipmentExtras, ShipmentMessageTemplate, ShipmentRequest,
                     ShipmentStatusLocation, SupportTicket)


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


class CityFilter(admin.SimpleListFilter):
    """Filter shipments by city"""
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


class ShipmentExtrasInline(admin.TabularInline):
    model = ShipmentExtras
    extra = 1
    verbose_name = "Extra"
    verbose_name_plural = "Extras"
    autocomplete_fields = ['extra']


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
        'user_link', 'staff_link', 'driver_link', 'city_link',
        'sender_name', 'recipient_name',
        'service_type', 'total_cost_display',  'receipt_download', 'id', 'created_at'
    ]
    list_filter = [
        'status', 'payment_method', 'payment_status',
        'service_type', 'created_at', StaffAssignmentFilter, DriverFilter, CityFilter
    ]
    search_fields = [
        'tracking_number', 'sender_name', 'recipient_name', 
        'current_location', 'user__email', 'staff__email',
        'driver__email', 'transaction_id', 'city__name'
    ]
    readonly_fields = [
        'tracking_number', 'tracking_history',
        'created_at', 'updated_at', 'receipt_download',
        'cod_amount', 'total_cost', 'delivery_charge', 'driver',
        'cost_breakdown_display'
    ]
    
    actions = [
        'assign_to_me',
        'unassign_staff',
        'mark_payment_as_paid',
        'mark_payment_as_failed',
        'assign_to_driver',
        'unassign_driver',
        'assign_to_city'
    ]
    
    inlines = [ShipmentExtrasInline]
    
    fieldsets = (
        ('Shipment Information', {
            'fields': (
                'tracking_number', 'status', 'user', 'staff', 'driver', 'city', 'notes'
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
        ('Package Information', {
            'fields': (
                'package_type', 'weight', ('length', 'width', 'height'),
                'description', 'declared_value'
            )
        }),
        ('Service Options', {
            'fields': (
                'service_type', 'insurance_required', 'signature_required'
            )
        }),
        ('Payment Information', {
            'fields': (
                ('payment_method', 'payment_status'),
                'payment_date', 'transaction_id'
            )
        }),
        ('Cost Information', {
            'fields': (
                'cost_breakdown_display',
                ('per_kg_rate', 'weight_charge'),
                ('total_additional_charges', 'extras_charges'),
                'delivery_charge', 'cod_amount', 'total_cost'
            ),
            'classes': ('wide',)
        }),
        ('Tracking Information', {
            'fields': (
                'current_location', 'tracking_history',
                'estimated_delivery', 'receipt_download'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
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
    
    def city_link(self, obj):
        if obj.city:
            url = reverse('admin:accounts_city_change', args=[obj.city.id])
            return format_html('<a href="{}">{}</a>', url, obj.city.name)
        return "-"
    city_link.short_description = 'City'
    
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
        self.message_user(
            request,
            "Drivers should be assigned automatically through city selection. "
            "Please use the 'Assign to City' action instead.",
            messages.WARNING
        )
        return None
    
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
        # Calculate subtotal
        subtotal = (
            obj.weight_charge +
            obj.total_additional_charges +
            obj.extras_charges
        )
        
        # Build detailed breakdown
        breakdown = f"""
            Weight Charge: ${obj.weight_charge:.2f}<br>
            Additional Charges: ${obj.total_additional_charges:.2f}<br>
            Extras Charges: ${obj.extras_charges:.2f}<br>
            <b>Subtotal: ${subtotal:.2f}</b><br>
        """
        
        # Add COD charge if applicable
        if obj.payment_method == 'COD' and obj.cod_amount > 0:
            breakdown += f"COD Charge (5%): ${obj.cod_amount:.2f}<br>"
            
        # Add delivery charge
        breakdown += f"<b>Delivery Charge: ${obj.delivery_charge:.2f}</b><br>"
        
        # Add total
        breakdown += f"<b>Total: ${obj.total_cost:.2f}</b>"
        
        return format_html(
            '<span title="{}" data-toggle="tooltip" data-html="true">${}</span>',
            breakdown,
            obj.total_cost
        )
    total_cost_display.short_description = 'Total Cost'
    
    def receipt_download(self, obj):
        if obj.receipt:
            return format_html(
                '<a href="{}" class="button" target="_blank">Download Receipt</a>',
                obj.receipt.url
            )
        return "-"
    receipt_download.short_description = 'Receipt'
    
    def delivery_charge_display(self, obj):
        return f"${obj.delivery_charge}"
    delivery_charge_display.short_description = 'Delivery Charge'
    
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
    
    def assign_to_city(self, request, queryset):
        """Action to assign selected shipments to a city"""
        if request.POST.get('city_id'):
            city_id = request.POST.get('city_id')
            try:
                city = City.objects.get(id=city_id, is_active=True)
                updated = queryset.update(
                    city=city,
                    delivery_charge=city.delivery_charge
                )
                
                # For each updated shipment, try to assign a driver
                for shipment in queryset:
                    # Get active drivers assigned to this city
                    driver_profiles = DriverProfile.objects.filter(
                        cities=city,
                        is_active=True
                    )
                    driver_profile = driver_profiles.first()
                    if driver_profile:
                        shipment.driver = driver_profile.user
                        shipment.save(update_fields=['driver'])
                
                self.message_user(
                    request,
                    f"{updated} shipments assigned to city {city.name}",
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
                <p>Select a city to assign the selected shipments to:</p>
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
    
    assign_to_city.short_description = "Assign selected shipments to city"

    def cost_breakdown_display(self, obj):
        """Display a formatted cost breakdown table"""
        # Calculate subtotal
        subtotal = (
            obj.weight_charge +
            obj.total_additional_charges +
            obj.extras_charges
        )
        
        # Format the main table beginning with professional styling
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
            .additional-details {
                margin-left: 20px;
                font-size: 12px;
                color: #555;
            }
        </style>
        <table class="cost-table">
            <tr>
                <th style="width: 70%">Cost Component</th>
                <th style="width: 30%">Amount</th>
            </tr>
            <tr>
                <td>Weight Charge (%.2f kg × $%.2f/kg = $%.2f)</td>
                <td>$%.2f</td>
            </tr>
        """ % (obj.weight, obj.per_kg_rate, obj.weight_charge, obj.weight_charge)
        
        # Get additional charges from related models
        from shipping_rates.models import AdditionalCharge, ShippingZone

        # Only add this section if there are additional charges
        if obj.total_additional_charges > 0:
            try:
                # Get the shipping zone
                shipping_zone = ShippingZone.objects.filter(
                    departure_countries=obj.sender_country,
                    destination_countries=obj.recipient_country,
                    is_active=True
                ).first()
                
                # Get additional charges details
                charges = AdditionalCharge.objects.filter(
                    zones=shipping_zone,
                    service_types=obj.service_type,
                    is_active=True
                )
                
                if charges.exists():
                    # Add a row for total additional charges
                    html += """
                    <tr>
                        <td>Additional Charges<div class="additional-details">
                    """
                    
                    # List each additional charge
                    for charge in charges:
                        charge_amount = Decimal('0.00')
                        if charge.charge_type == 'FIXED':
                            charge_amount = charge.value
                        else:  # PERCENTAGE
                            charge_amount = (obj.weight_charge * charge.value / 100)
                            
                        charge_amount = round(charge_amount, 2)
                        
                        charge_type_display = "Fixed" if charge.charge_type == 'FIXED' else f"{charge.value}%"
                        html += f"• {charge.name} ({charge_type_display}): ${charge_amount:.2f}<br>"
                    
                    html += """
                        </div></td>
                        <td>$%.2f</td>
                    </tr>
                    """ % obj.total_additional_charges
                else:
                    # Just show the total if we can't get the details
                    html += """
                    <tr>
                        <td>Additional Charges</td>
                        <td>$%.2f</td>
                    </tr>
                    """ % obj.total_additional_charges
            except Exception:
                # Fallback in case of error
                html += """
                <tr>
                    <td>Additional Charges</td>
                    <td>$%.2f</td>
                </tr>
                """ % obj.total_additional_charges
        
        # Get extras details
        extras = list(obj.shipmentextras_set.select_related('extra').all())
        
        if extras:
            # Add a row for extras charges
            html += """
            <tr>
                <td>Extras Charges<div class="additional-details">
            """
            
            # List each extra
            for shipment_extra in extras:
                extra = shipment_extra.extra
                quantity = shipment_extra.quantity
                
                # Calculate the charge
                extra_charge = Decimal('0.00')
                if extra.charge_type == 'FIXED':
                    extra_charge = extra.value * quantity
                else:  # PERCENTAGE
                    extra_charge = (obj.weight_charge * extra.value / 100) * quantity
                
                extra_charge = round(extra_charge, 2)
                
                charge_type_display = "Fixed" if extra.charge_type == 'FIXED' else f"{extra.value}%"
                html += f"• {extra.name} × {quantity} ({charge_type_display}): ${extra_charge:.2f}<br>"
            
            html += """
                </div></td>
                <td>$%.2f</td>
            </tr>
            """ % obj.extras_charges
        else:
            # No extras
            html += """
            <tr>
                <td>Extras Charges</td>
                <td>$0.00</td>
            </tr>
            """
        
        # Add subtotal
        html += """
        <tr class="subtotal">
            <td>Subtotal</td>
            <td>$%.2f</td>
        </tr>
        """ % subtotal
        
        # Add COD charge if applicable
        if obj.payment_method == 'COD' and obj.cod_amount > 0:
            cod_html = """
            <tr>
                <td>COD Charge (5%%)</td>
                <td>$%.2f</td>
            </tr>
            """ % obj.cod_amount
            html += cod_html
        
        # Add delivery charge and total
        footer_html = """
        <tr>
            <td>Delivery Charge</td>
            <td>$%.2f</td>
        </tr>
        <tr class="total">
            <td>Total Cost</td>
            <td>$%.2f</td>
        </tr>
        </table>
        """ % (obj.delivery_charge, obj.total_cost)
        html += footer_html
        
        # Use mark_safe instead of format_html since we're already handling the formatting
        return mark_safe(html)
    cost_breakdown_display.short_description = 'Cost Breakdown'

    def save_model(self, request, obj, form, change):
        """Mark instance as coming from admin panel to trigger recalculation"""
        obj._from_admin = True
        super().save_model(request, obj, form, change)


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
                'status',
                'admin_reply'
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


@admin.register(ShipmentMessageTemplate)
class ShipmentMessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_type', 'get_template_type_display', 'subject', 'is_active', 'updated_at']
    list_filter = ['template_type', 'is_active']
    search_fields = ['subject', 'message_content']
    readonly_fields = ['created_at', 'updated_at', 'preview_template']
    fieldsets = (
        (None, {
            'fields': ('template_type', 'subject', 'is_active')
        }),
        ('Message Content', {
            'fields': ('message_content',),
            'description': 'Use placeholders like {recipient_name}, {sender_name}, {tracking_number}, etc.'
        }),
        ('Preview', {
            'fields': ('preview_template',),
            'description': 'This shows how the template will look with sample data.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_template_type_display(self, obj):
        return obj.get_template_type_display()
    get_template_type_display.short_description = 'Template Type'
    
    def preview_template(self, obj):
        """Display a preview of the template with sample data"""
        if obj.id:  # Only if the object has been saved
            preview = obj.preview_with_sample_data()
            return mark_safe(f'<div style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;">'
                            f'<pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{preview}</pre>'
                            f'</div>')
        return "Save the template first to see a preview."
    preview_template.short_description = 'Preview'
    
    def save_model(self, request, obj, form, change):
        """Save the model and create default templates if needed"""
        super().save_model(request, obj, form, change)
        
        # When adding a new template, check if we need to create other default templates
        if not change:  # This is a new template
            self._create_default_templates()
            
    def _create_default_templates(self):
        """Create default templates for all template types if they don't exist"""
        template_types = ShipmentMessageTemplate.TemplateType.choices
        existing_types = set(ShipmentMessageTemplate.objects.values_list('template_type', flat=True))
        
        for template_type, display_name in template_types:
            if template_type not in existing_types:
                # Create default template based on type
                if template_type == 'confirmation':
                    ShipmentMessageTemplate.objects.create(
                        template_type=template_type,
                        subject='Your Shipment Has Been Confirmed',
                        message_content="""Dear {recipient_name},

Your shipment has been confirmed and is now being processed. You can track your shipment using tracking number: {tracking_number}.

Shipment Details:
- Sender: {sender_name}
- From: {sender_country}
- Package Type: {package_type}
- Weight: {weight} kg
- Dimensions: {dimensions} cm

Estimated delivery date: {estimated_delivery}.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
                    )
                elif template_type == 'notification':
                    ShipmentMessageTemplate.objects.create(
                        template_type=template_type,
                        subject='Your Shipment Is On The Way',
                        message_content="""Dear {recipient_name},

We'd like to inform you that a package from {sender_name} in {sender_country} is on its way to you. The tracking number for this shipment is: {tracking_number}.

Current Status: {status}
Current Location: {current_location}

Shipment Origin: {sender_country}
Sender Contact: {sender_email} / {sender_phone}

Our delivery team will contact you prior to delivery. Please ensure someone is available to receive the package.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
                    )
                elif template_type == 'delivery':
                    ShipmentMessageTemplate.objects.create(
                        template_type=template_type,
                        subject='Your Package Is Out For Delivery',
                        message_content="""Dear {recipient_name},

Good news! Your package from {sender_name} in {sender_country} is out for delivery today. Please ensure someone is available at the delivery address to receive the package.

Tracking Number: {tracking_number}
Package Type: {package_type}
Weight: {weight} kg

If you have any special delivery instructions, please contact our customer service team immediately.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
                    )
                elif template_type == 'custom':
                    ShipmentMessageTemplate.objects.create(
                        template_type=template_type,
                        subject='Update On Your Shipment',
                        message_content="""Dear {recipient_name},

We have an update regarding your shipment from {sender_country}. Tracking Number: {tracking_number}
Current Status: {status}

Sender: {sender_name}
Origin: {sender_country}

Please check our website or tracking portal for more details.

Thank you for choosing Grade-A Express for your shipping needs.

Best regards,
The Grade-A Express Team"""
                    )
