import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "local-synthetic-demo-only-change-for-any-other-use")
DEBUG = os.environ.get("DEMO_MODE") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "reconciliation",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "invoice_recon"),
        "USER": os.environ.get("PGUSER", "dw"),
        "HOST": os.environ.get(
            "PGHOST", "/Users/dw/code/portfolio-python/.runtime/pg16/invoice/socket"
        ),
        "PORT": os.environ.get("PGPORT", "15532"),
    }
}
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 300000
