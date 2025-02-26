from django.apps import AppConfig


class ShipmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shipments"

    def ready(self):
        """Import signals when the app is ready"""
        from . import signals  # This will register our signals
