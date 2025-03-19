from django.contrib import admin
from django.utils.html import format_html

from .models import (AdditionalCharge, Country, Currency, DimensionalFactor,
                     Extras, ServiceType, ShippingZone, WeightBasedRate)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'country_type', 'zone_count', 'is_active', 'id']
    list_filter = ['is_active', 'country_type']
    readonly_fields = ['id']
    search_fields = ['name', 'code']
    ordering = ['name']
    
    def zone_count(self, obj):
        if obj.country_type == Country.CountryType.DEPARTURE:
            return obj.departure_zones.count()
        return obj.destination_zones.count()
    zone_count.short_description = 'Zones'

@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'departure_countries_display', 
        'destination_countries_display', 'rate_count', 
        'is_active'
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    filter_horizontal = ['departure_countries', 'destination_countries']
    
    def departure_countries_display(self, obj):
        return ", ".join([c.code for c in obj.departure_countries.all()])
    departure_countries_display.short_description = 'Departure Countries'
    
    def destination_countries_display(self, obj):
        return ", ".join([c.code for c in obj.destination_countries.all()])
    destination_countries_display.short_description = 'Destination Countries'
    
    def rate_count(self, obj):
        return obj.weightbasedrate_set.count()
    rate_count.short_description = 'Rates'

@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'delivery_time', 'price_display',
        'is_active', 'id'
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['id']
    
    def price_display(self, obj):
        return format_html('<b>RM {}</b>', obj.price)
    price_display.short_description = 'Service Price'

@admin.register(WeightBasedRate)
class WeightBasedRateAdmin(admin.ModelAdmin):
    list_display = [
        'zone', 'service_type', 'weight_range', 
        'regulation_charge_display', 'per_kg_rate_display', 'is_active'
    ]
    list_filter = ['is_active', 'zone', 'service_type']
    search_fields = ['zone__name', 'service_type__name']
    
    def weight_range(self, obj):
        return f"{obj.min_weight}kg - {obj.max_weight}kg"
    weight_range.short_description = 'Weight Range'
    
    def regulation_charge_display(self, obj):
        return format_html('<b>${}</b>', obj.regulation_charge)
    regulation_charge_display.short_description = 'Base Rate'
    
    def per_kg_rate_display(self, obj):
        return format_html('<b>${}/kg</b>', obj.per_kg_rate)
    per_kg_rate_display.short_description = 'Per KG Rate'

@admin.register(DimensionalFactor)
class DimensionalFactorAdmin(admin.ModelAdmin):
    list_display = ['service_type', 'factor', 'is_active']
    list_filter = ['is_active', 'service_type']
    search_fields = ['service_type__name']

@admin.register(AdditionalCharge)
class AdditionalChargeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'charge_type', 'value_display', 
        'zone_count', 'service_type_count', 'is_active'
    ]
    list_filter = ['is_active', 'charge_type', 'zones', 'service_types']
    search_fields = ['name', 'description']
    filter_horizontal = ['zones', 'service_types']
    
    def value_display(self, obj):
        if obj.charge_type == 'PERCENTAGE':
            return format_html('<b>{}%</b>', obj.value)
        return format_html('<b>${}</b>', obj.value)
    value_display.short_description = 'Value'
    
    def zone_count(self, obj):
        return obj.zones.count()
    zone_count.short_description = 'Zones'
    
    def service_type_count(self, obj):
        return obj.service_types.count()
    service_type_count.short_description = 'Service Types'



# @admin.register(Extras)
# class CountryAdmin(admin.ModelAdmin):
#     list_display = ['name', 'charge_type', 'value', 'is_active', 'id']
#     list_filter = ['is_active']
#     readonly_fields = ['id']
#     search_fields = ['name', 'value', 'charge_type']
#     ordering = ['name']

admin.site.register(Currency)