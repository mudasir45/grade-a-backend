from rest_framework import permissions


class IsStaffUser(permissions.BasePermission):
    """
    Custom permission to only allow staff members to access the view.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff 