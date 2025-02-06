"""
Base settings shared across all environments
"""
from datetime import timedelta
from pathlib import Path
import os
import environ

# Initialize environ
env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_ENV=(str, "development"),
    ALLOWED_HOSTS=(list, []),
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# Application definition
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    
    # Local apps
    'accounts',
    'buy4me',
    'reports',
    'shipments',
    'vendors',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(env('JWT_ACCESS_TOKEN_LIFETIME', default=500))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(env('JWT_REFRESH_TOKEN_LIFETIME', default=500))),
    'ROTATE_REFRESH_TOKENS': True,
}

# Add Spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Grade-A Express API',
    'DESCRIPTION': 'API for logistics and Buy4Me services',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Optional UI customization
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    
    # Optional: Tags to group endpoints
    'TAGS': [
        {'name': 'auth', 'description': 'Authentication endpoints'},
        {'name': 'users', 'description': 'User management endpoints'},
        {'name': 'shipments', 'description': 'Shipment management endpoints'},
        {'name': 'buy4me', 'description': 'Buy4Me service endpoints'},
    ],
    
    # Security schemes
    'SECURITY': [
        {
            'Bearer': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    ],
} 