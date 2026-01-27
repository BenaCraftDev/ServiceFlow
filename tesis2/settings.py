from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import os


# Configuración para Railway
if 'RAILWAY_ENVIRONMENT' in os.environ:
    # ← ESTA LÍNEA SOLUCIONA EL ERROR 400
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    DEBUG = False
    ALLOWED_HOSTS = ['.railway.app', '.up.railway.app']
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    # Desarrollo local
    DEBUG = True
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-in-production")

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'https://serviceflow-production.up.railway.app',
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/panel-empleados/'
LOGOUT_REDIRECT_URL = '/'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'home',
    'cotizaciones',
    'notificaciones',
    'app_movil',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'home.middleware.PerfilEmpleadoMiddleware',
]

ROOT_URLCONF = 'tesis2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'),],
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

WSGI_APPLICATION = 'tesis2.wsgi.application'


# Database - Configuración inteligente según el entorno
# Detecta si estamos en Railway o en desarrollo local
if os.environ.get('RAILWAY_ENVIRONMENT'):
    # PRODUCCIÓN: Railway (usa DATABASE_URL automáticamente)
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # DESARROLLO LOCAL: Usa la configuración local antigua
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'electromecanicos_db',
            'USER': 'django_user',
            'PASSWORD': '246eb866f69f',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Santiago'
# Formato de fechas en formularios HTML5
DATE_INPUT_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']

# Formato de fecha/hora en formularios HTML5
DATETIME_INPUT_FORMATS = [
    '%Y-%m-%d %H:%M:%S',     # '2025-12-16 14:30:00'
    '%Y-%m-%d %H:%M',        # '2025-12-16 14:30'
    '%Y-%m-%d',              # '2025-12-16'
    '%d/%m/%Y %H:%M:%S',     # '16/12/2025 14:30:00'
    '%d/%m/%Y %H:%M',        # '16/12/2025 14:30'
    '%d/%m/%Y',              # '16/12/2025'
]

USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise - Sirve archivos estáticos en producción
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email con Gmail
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.resend.com'
EMAIL_PORT = 465
EMAIL_USE_TLS = False
EMAIL_USE_SSL = True
EMAIL_HOST_USER = 'resend'
EMAIL_HOST_PASSWORD = 're_HMF8LkGF_PkdVHbHUA2xHywReQGGkejLU'
DEFAULT_FROM_EMAIL = 'cotizaciones@gatwo.xyz'

# Timeout para emails
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 30))

# Logging para emails
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'cotizaciones.email_utils': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.core.mail': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# CORS - Permitir acceso desde React Native
CORS_ALLOW_ALL_ORIGINS = True  # Para desarrollo
CORS_ALLOW_CREDENTIALS = True