"""
Django settings for urbix project.

Integrated with HR Payroll system configurations.
Production-ready with comprehensive security and deployment settings.
"""

import os
import dj_database_url
from decouple import config
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-this-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

# Production-ready allowed hosts
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".onrender.com",
    config("DOMAIN_NAME", default=""),
]

# Custom User Model (from HR system)
AUTH_USER_MODEL = "accounts.CustomUser"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # HR system static file handling
    "django.contrib.staticfiles",
    # Third party apps
    "webpack_loader",  # URBIX webpack integration
    "django_extensions",  # HR system
    "django_celery_beat",  # HR system background tasks
    # Local apps from HR system
    "accounts",
    "core",
    "employees",
    "attendance",
    "payroll",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # HR system static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "urbix.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "urbix.wsgi.application"

# Database Configuration (HR system enhanced)
if config("DATABASE_URL", default=None):
    # Production Database (PostgreSQL from Render)
    DATABASES = {"default": dj_database_url.parse(config("DATABASE_URL"))}
else:
    # Development Database (SQLite)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization (HR system enhanced)
LANGUAGE_CODE = "en-us"
TIME_ZONE = config(
    "TIME_ZONE", default="Asia/Colombo"
)  # HR system default, configurable
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images) - Combined URBIX + HR system
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Combined static files directories
STATICFILES_DIRS = []
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS.append(BASE_DIR / "static")

# WhiteNoise configuration for static files (HR system)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files (User uploads) - HR system
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Webpack loader config (URBIX preserved)
WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "STATS_FILE": BASE_DIR / "static/assets/webpack-stats.json",
    }
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication URLs (HR system)
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/"

# Celery Configuration (Background Tasks) - HR system
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Email Configuration (HR system)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@urbix.com")

# File Upload Settings (HR system)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644

# Production Security Settings (HR system)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# SSL/HTTPS Settings (Production) - HR system
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Guardian (Object-level permissions) - HR system
AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

# Session Configuration (HR system)
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# CSRF Configuration (HR system)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    config("CSRF_TRUSTED_ORIGIN", default="http://localhost:8000"),
]

# Cache Configuration (HR system)
if config("REDIS_URL", default=None):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": config("REDIS_URL"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

# Logging Configuration (HR system)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "urbix": {  # Updated for URBIX project
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Payroll Specific Settings (HR system)
PAYROLL_SETTINGS = {
    "DEFAULT_CURRENCY": "LKR",  # Sri Lankan Rupees
    "TAX_RATE": 0.15,  # 15% default tax rate
    "OVERTIME_MULTIPLIER": 1.5,
    "WORKING_HOURS_PER_DAY": 8,
    "WORKING_DAYS_PER_WEEK": 5,
    "MINIMUM_WAGE": 15000,  # LKR per month
}

# HR System Settings (HR system)
HR_SETTINGS = {
    "EMPLOYEE_CODE_PREFIX": "EMP",
    "EMPLOYEE_CODE_LENGTH": 6,
    "PASSWORD_RESET_TIMEOUT": 3600,  # 1 hour
    "MAX_LOGIN_ATTEMPTS": 5,
    "ACCOUNT_LOCKOUT_DURATION": 1800,  # 30 minutes
    "SESSION_TIMEOUT": 3600,  # 1 hour
}

# License System Settings (HR system)
LICENSE_SETTINGS = {
    "OFFLINE_VALIDATION_DAYS": 30,
    "LICENSE_CHECK_INTERVAL": 24,  # hours
    "TRIAL_PERIOD_DAYS": 14,
    "MAX_EMPLOYEES": 1000,
}

# Internationalization Settings (HR system)
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

ANONYMOUS_USER_NAME = None

# Date and Time Formats (HR system)
DATE_FORMAT = "Y-m-d"
TIME_FORMAT = "H:i:s"
DATETIME_FORMAT = "Y-m-d H:i:s"
SHORT_DATE_FORMAT = "m/d/Y"
SHORT_DATETIME_FORMAT = "m/d/Y P"

# Number Formatting (HR system)
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ","
DECIMAL_SEPARATOR = "."

# Development Settings (HR system enhanced)
if DEBUG:
    try:
        import debug_toolbar

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        INTERNAL_IPS = ["127.0.0.1", "localhost"]
    except ImportError:
        pass

# Environment indicator (HR system)
RENDER = config("RENDER", default=False, cast=bool)
