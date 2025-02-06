"""
Development-specific settings
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# Email settings for development (console backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Debug Toolbar settings
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1']

# Disable axes in development
AXES_ENABLED = False 