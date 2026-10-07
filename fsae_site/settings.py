"""Django settings for the handoff-friendly FSAE team website."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def _read_env(name, default=None):
    """Read a value from an environment variable or a mounted secret file."""
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        try:
            return Path(file_name).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(f"Unable to read {name}_FILE") from exc
    return os.getenv(name, default)


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean")


def _env_list(name, default=""):
    return [item.strip() for item in _read_env(name, default).split(",") if item.strip()]


DEBUG = _env_bool("DJANGO_DEBUG", False)

SECRET_KEY = _read_env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "local-development-only-change-me"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE is required")

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    if DEBUG:
        ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    else:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG is false")

# The container health check runs locally, while public hosts are configured
# separately through DJANGO_ALLOWED_HOSTS.
if not DEBUG:
    ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, "localhost", "127.0.0.1"]))

TEAM_NAME = os.getenv("TEAM_NAME", "ELECTRIC STING RACING")
TEAM_SCHOOL = os.getenv("TEAM_SCHOOL", "SACRAMENTO STATE")
TEAM_LOCATION = os.getenv("TEAM_LOCATION", "Sacramento State / Engineering & Computer Science")
TEAM_EMAIL = os.getenv("TEAM_EMAIL", "electricstingracing@sacstate.edu")
TEAM_SEASON = os.getenv("TEAM_SEASON", "2026 — 2027")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "team",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fsae_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "team.context_processors.branding",
            ],
        },
    }
]

WSGI_APPLICATION = "fsae_site.wsgi.application"
ASGI_APPLICATION = "fsae_site.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite" if DEBUG else "postgres").lower()
if not DEBUG and DB_ENGINE not in {"postgres", "postgresql"}:
    raise ImproperlyConfigured("Production deployments must use PostgreSQL")

if DB_ENGINE in {"postgres", "postgresql"}:
    db_password = _read_env("DB_PASSWORD", "")
    if not db_password and not DEBUG:
        raise ImproperlyConfigured("DB_PASSWORD or DB_PASSWORD_FILE is required")

    postgres_options = {}
    db_sslmode = os.getenv("DB_SSLMODE")
    if db_sslmode:
        postgres_options["sslmode"] = db_sslmode

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "fsae"),
            "USER": os.getenv("DB_USER", "fsae_app"),
            "PASSWORD": db_password,
            "HOST": os.getenv("DB_HOST", "db"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": postgres_options,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TZ", "America/Los_Angeles")
USE_I18N = True
USE_TZ = True

CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS is required when DJANGO_DEBUG is false")

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

SENTRY_DSN = _read_env("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )
