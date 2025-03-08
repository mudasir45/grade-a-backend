from rest_framework import permissions


class IsDriver(permissions.BasePermission):
    """
    Custom permission to only allow drivers to access the view.
    """
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'DRIVER'


class IsDriverOrStaff(permissions.BasePermission):
    """
    Custom permission to allow both drivers and staff members to access the view.
    """
    def has_permission(self, request, view):
        if not request.user:
            return False
        return request.user.user_type == 'DRIVER' or request.user.is_staff
    
    
class IsDriverForShipment(permissions.BasePermission):
    """
    Permission to only allow the assigned driver to update a specific shipment.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user:
            return False
        
        # Check if the user is the assigned driver
        return obj.driver and obj.driver.id == request.user.id 