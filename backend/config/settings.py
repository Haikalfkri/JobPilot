from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)
# .env ada di root project (satu level di atas backend/).
# Kalau tidak ada tidak masalah, Docker menyuntikkan variabelnya langsung.
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "drf_spectacular",
    "core",
    "resumes",
    "jobs",
    "matching",
    "ai_engine",
    "applications",
    "automation",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SimpleCorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# PostgreSQL by default. Kalau DATABASE_URL diset (misal sqlite untuk tes), itu yang dipakai.
if env("DATABASE_URL", default=None):
    DATABASES = {"default": env.db_url("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="jobpilot"),
            "USER": env("POSTGRES_USER", default="jobpilot"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="jobpilot"),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_TIMEZONE = env("TIME_ZONE", default="Asia/Jakarta")

OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://localhost:11434")

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}
SPECTACULAR_SETTINGS = {"TITLE": "JobPilot API", "VERSION": "0.1.0"}

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Jakarta")
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR.parent / "data" / "media"))

# Resume uploads
MAX_RESUME_UPLOAD_BYTES = env.int("MAX_RESUME_UPLOAD_MB", default=5) * 1024 * 1024
RESUME_MAX_PAGES = env.int("RESUME_MAX_PAGES", default=30)


# Job discovery
DISCOVERY_DEFAULT_KEYWORDS = env.list(
    "DISCOVERY_DEFAULT_KEYWORDS", default=["python", "django", "backend", "software engineer", "developer"]
)
DISCOVERY_MAX_KEYWORDS = env.int("DISCOVERY_MAX_KEYWORDS", default=5)
DISCOVERY_REQUEST_DELAY_SECONDS = env.float("DISCOVERY_REQUEST_DELAY_SECONDS", default=1.0)
DISCOVERY_REQUEST_TIMEOUT_SECONDS = env.float("DISCOVERY_REQUEST_TIMEOUT_SECONDS", default=15.0)
DISCOVERY_ARBEITNOW_MAX_PAGES = env.int("DISCOVERY_ARBEITNOW_MAX_PAGES", default=3)

# Optional daily discovery run via Celery Beat (off by default; sources ask for a few calls per day at most).
if env.bool("DISCOVERY_SCHEDULE_ENABLED", default=False):
    from celery.schedules import crontab

    CELERY_BEAT_SCHEDULE = {
        "scheduled-job-discovery": {
            "task": "jobs.tasks.scheduled_discovery_task",
            "schedule": crontab(hour=env.int("DISCOVERY_SCHEDULE_HOUR", default=7), minute=0),
        }
    }