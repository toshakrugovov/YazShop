from pathlib import Path
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# ================== Пути ==================
BASE_DIR = Path(__file__).resolve().parent.parent

# ================== Секрет и отладка ==================
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-s=gsg*^y^b&gzj9=v67@es*wdg&fzy-fmo-ox$2fq0e(oc+h3l')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ================== Приложения ==================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',  # Для обслуживания статических файлов в DEBUG режиме
    'rest_framework',
    'drf_yasg',
    'main',
    
]

# ================== Middleware ==================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Для обслуживания статических файлов в продакшене
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'main.middleware.BlockedUserMiddleware',  # Проверка блокировки пользователя (после AuthenticationMiddleware)
    'main.middleware.AdminAccessMiddleware',
]

# ================== URLs ==================
ROOT_URLCONF = 'yazshop.urls'

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

WSGI_APPLICATION = 'yazshop.wsgi.application'

# ================== База данных ==================
# Для продакшена рекомендуется использовать PostgreSQL
# Для разработки можно использовать SQLite
if os.environ.get('DATABASE_URL'):
    # PostgreSQL (продакшен)
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
        }
    except ImportError:
        # Если dj_database_url не установлен, используем SQLite
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    # SQLite (разработка)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ================== Валидация пароля ==================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ================== Локализация ==================
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# ================== Статические файлы ==================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'main' / 'static'
]

# WhiteNoise для обслуживания статических файлов
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ================== Медиа ==================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ================== Сессии и Cookies ==================
# Для продакшена с HTTPS установите в True
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'False') == 'True'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

# ================== Переменные по умолчанию ==================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================== Login ==================
LOGIN_URL = '/login/'                # redirect при @login_required
LOGIN_REDIRECT_URL = '/profile/'     # куда редирект после login()
LOGOUT_REDIRECT_URL = '/'

# ================== Django REST Framework ==================
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ================== Настройки кастомного пользователя (если будет) ==================
# AUTH_USER_MODEL = 'main.User'  # Раскомментировать, если есть кастомная модель
