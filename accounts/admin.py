# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Contact, Store, User, UserCountry


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'username', 'user_type', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'is_verified')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'address', 'country', 'default_shipping_method', 'preferred_currency')}),
        (_('Permissions'), {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    ) 
    
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'id')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('-created_at',)
    
@admin.register(UserCountry)
class UserCountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at', 'updated_at', 'id')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'code')
    ordering = ('-created_at',)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'status', 'created_at', 'id')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'phone', 'subject', 'message', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'email', 'phone', 'subject', 'message')
        }),
        (_('Admin'), {
            'fields': ('status', 'admin_notes')
        }),
        (_('Dates'), {
            'fields': ('created_at',)
        }),
    )
    ordering = ('-created_at',)
