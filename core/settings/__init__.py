"""
Django settings module initialization.
Import the appropriate settings based on the environment.
"""
import os

# Default to development settings
environment = os.getenv('DJANGO_ENV', 'development')

if environment == 'production':
    from .production import *
elif environment == 'staging':
    from .staging import *
else:
    from .development import * 