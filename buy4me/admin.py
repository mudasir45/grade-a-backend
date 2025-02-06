from django.contrib import admin
from .models import Buy4MeRequest, Buy4MeItem

class Buy4MeItemInline(admin.TabularInline):
    model = Buy4MeItem
    extra = 0

@admin.register(Buy4MeRequest)
class Buy4MeRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'total_cost', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'user__email']
    inlines = [Buy4MeItemInline]
    readonly_fields = ['total_cost']

@admin.register(Buy4MeItem)
class Buy4MeItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'buy4me_request', 'product_name', 'quantity', 'unit_price']
    search_fields = ['product_name']
    list_filter = ['created_at']
