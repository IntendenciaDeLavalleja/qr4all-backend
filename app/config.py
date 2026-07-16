import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _BASE_DIR / '.env'

# Load backend/.env when present without overriding injected env vars.
load_dotenv(_DOTENV_PATH, override=False)

# ─────────────────────────────────────────────────────────────────────────────
# QR4All Lavalleja – Flask Configuration
# ─────────────────────────────────────────────────────────────────────────────


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Robust boolean parser for env vars (True/False/true/false/1/0/yes/no)."""
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _normalize_origin(value: str | None) -> str:
    if not value:
        return ''
    return value.strip().strip('"').strip("'").rstrip('/')


def _parse_cors_origins(
    raw_value: str | None,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    candidates = raw_value.split(',') if raw_value else fallback
    normalized: list[str] = []
    seen: set[str] = set()

    for item in candidates:
        origin = _normalize_origin(item)
        if not origin:
            continue
        key = origin.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(origin)

    return tuple(normalized) or fallback


def _hostname_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    return parsed.hostname


_WEAK_SECRET_PLACEHOLDERS = {
    '',
    'change-me',
    'change-me-in-production-please',
    'changeme',
    'secret',
    'test',
    'dev',
}


def _is_weak_secret(value: str | None) -> bool:
    if not value:
        return True
    lower = value.strip().lower()
    return (
        not lower
        or lower in _WEAK_SECRET_PLACEHOLDERS
        or ('change' in lower and 'me' in lower)
    )


class Config:
    # Deployment mode: 'local' (Windows venv) or 'coolify' (Docker/Coolify).
    # Controls host validation so Docker-only hostnames like 'db', 'redis',
    # 'minio' are caught early with a clear message instead of obscure DNS
    # failures.
    DEPLOYMENT_MODE = (
        os.environ.get('DEPLOYMENT_MODE') or 'local'
    ).strip().lower()

    ENV_NAME = (os.environ.get('FLASK_ENV') or 'production').strip().lower()
    SECRET_KEY = (
        os.environ.get('SECRET_KEY')
        or 'change-me-in-production-please'
    )

    # Database — canonical: DATABASE_URL. Legacy fallback: DATABASE_URI.
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('DATABASE_URI')
        or 'sqlite:///gvl.db'
    )
    if not SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE') or 280),
            'pool_size': int(os.environ.get('DB_POOL_SIZE') or 10),
            'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW') or 20),
            'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT') or 30),
        }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = _as_bool(os.environ.get('MAIL_USE_TLS'), default=True)
    MAIL_USE_SSL = _as_bool(os.environ.get('MAIL_USE_SSL'), default=False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = (
        os.environ.get('MAIL_DEFAULT_SENDER')
        or 'noreply@gvl.local'
    )

    # App identity
    APP_NAME = os.environ.get('APP_NAME', 'QR4All Lavalleja')
    FRONTEND_URL = _normalize_origin(
        os.environ.get('FRONTEND_URL')
    )
    # Canonical: PUBLIC_API_BASE_URL. Legacy fallback: PUBLIC_BASE_URL.
    PUBLIC_API_BASE_URL = _normalize_origin(
        os.environ.get('PUBLIC_API_BASE_URL')
        or os.environ.get('PUBLIC_BASE_URL')
    ) or FRONTEND_URL or 'http://localhost:5000'

    # IP hashing
    IP_HASH_SALT = os.environ.get('IP_HASH_SALT') or SECRET_KEY

    # WTF / CSRF (admin HTML panel)
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or SECRET_KEY

    # Session security (admin HTML panel uses server-side sessions)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = not _as_bool(
        os.environ.get('FLASK_DEBUG'),
        default=False,
    )
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour admin session

    # Prometheus multiprocess directory (set by entrypoint in production)
    PROMETHEUS_MULTIPROC_DIR = os.environ.get('PROMETHEUS_MULTIPROC_DIR')

    # Redis — canonical: REDIS_URL. Gracefully degrades if unset/unavailable.
    # init_redis() probes at startup and sets REDIS_AVAILABLE.
    REDIS_URL = (os.environ.get('REDIS_URL') or '').strip()

    # Flask-Limiter reads RATELIMIT_STORAGE_URL (not *_URI). We keep
    # RATELIMIT_STORAGE_URI for backward compatibility with existing env files
    # but expose the canonical key so the limiter actually uses it.
    _storage_url = (
        os.environ.get('RATELIMIT_STORAGE_URL')
        or os.environ.get('RATELIMIT_STORAGE_URI')
        or 'memory://'
    )
    RATELIMIT_STORAGE_URL = _storage_url
    RATELIMIT_STORAGE_URI = _storage_url

    # Local dummy auth (development/testing only)
    ENABLE_LOCAL_DUMMY_AUTH = _as_bool(
        os.environ.get('ENABLE_LOCAL_DUMMY_AUTH'),
        default=False,
    )
    LOCAL_DUMMY_EMAIL = os.environ.get('LOCAL_DUMMY_EMAIL', 'admin@qr4all.dev')
    LOCAL_DUMMY_PASSWORD = os.environ.get('LOCAL_DUMMY_PASSWORD', 'Admin1234!')
    LOCAL_DUMMY_2FA_CODE = os.environ.get('LOCAL_DUMMY_2FA_CODE', '123456')

    # CORS – origins loaded exclusively from env vars; no hardcoded fallback.
    CORS_ORIGINS_RAW = os.environ.get('CORS_ORIGINS')
    _frontend_fallback = (FRONTEND_URL,) if FRONTEND_URL else ()
    CORS_ALLOWED_ORIGINS = list(
        _parse_cors_origins(CORS_ORIGINS_RAW, _frontend_fallback)
    )
    CORS_ALLOW_HEADERS = (
        'Authorization',
        'Content-Type',
        'X-Requested-With',
    )
    CORS_METHODS = (
        'GET',
        'POST',
        'PUT',
        'PATCH',
        'DELETE',
        'OPTIONS',
    )
    CORS_SUPPORTS_CREDENTIALS = True

    # QR logo uploads
    QR_LOGO_MAX_SIZE_BYTES = int(
        os.environ.get('QR_LOGO_MAX_SIZE_BYTES') or (2 * 1024 * 1024)
    )
    QR_LOGO_ALLOWED_MIMETYPES = {
        'image/png',
        'image/jpeg',
        'image/webp',
    }

    # MinIO / S3-compatible object storage (for QR logos and future uploads)
    MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT')
    MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY')
    MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY')
    # Canonical: MINIO_BUCKET_NAME. Legacy fallback: MINIO_BUCKET.
    MINIO_BUCKET_NAME = (
        os.environ.get('MINIO_BUCKET_NAME')
        or os.environ.get('MINIO_BUCKET')
    )
    MINIO_SECURE = _as_bool(os.environ.get('MINIO_SECURE'), default=True)
    # Canonical: MINIO_PUBLIC_URL. Legacy fallback: MINIO_PUBLIC_BASE_URL.
    MINIO_PUBLIC_URL = (
        os.environ.get('MINIO_PUBLIC_URL')
        or os.environ.get('MINIO_PUBLIC_BASE_URL')
    )

    # ─────────────────────────────────────────────────────────────────────
    # Production hardening
    # ─────────────────────────────────────────────────────────────────────
    _is_production = ENV_NAME == 'production'

    if _is_production:
        _prod_errors: list[str] = []
        if _is_weak_secret(os.environ.get('SECRET_KEY')):
            _prod_errors.append("SECRET_KEY must be set to a strong random value.")
        if _is_weak_secret(os.environ.get('WTF_CSRF_SECRET_KEY')):
            _prod_errors.append("WTF_CSRF_SECRET_KEY must be set to a strong random value.")
        if not os.environ.get('DATABASE_URL') and not os.environ.get('DATABASE_URI'):
            _prod_errors.append("DATABASE_URL is required in production.")
        if not os.environ.get('PUBLIC_API_BASE_URL') and not os.environ.get('PUBLIC_BASE_URL'):
            _prod_errors.append("PUBLIC_API_BASE_URL is required in production.")
        if not os.environ.get('FRONTEND_URL'):
            _prod_errors.append("FRONTEND_URL is required in production.")
        _cors_raw = (os.environ.get('CORS_ORIGINS') or '').strip()
        if _cors_raw == '*' or _cors_raw == '':
            _prod_errors.append("CORS_ORIGINS must be set to the real frontend domain(s) in production (no wildcard).")
        if _as_bool(os.environ.get('FLASK_DEBUG')):
            _prod_errors.append("FLASK_DEBUG must be 0 in production.")
        for _var in ('SECRET_KEY', 'WTF_CSRF_SECRET_KEY', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY'):
            _val = os.environ.get(_var) or ''
            if _val and 'change_me' in _val.lower():
                _prod_errors.append(f"{_var} contains a placeholder (CHANGE_ME). Set a real value.")
        if _prod_errors:
            raise ValueError(
                "Production configuration errors:\n"
                + "\n".join(f"  - {e}" for e in _prod_errors)
            )

    # ─────────────────────────────────────────────────────────────────────
    # Deployment-mode host validation
    # Prevents confusing DNS failures when running locally with Coolify
    # hostnames (db, redis, minio) or vice-versa.
    # ─────────────────────────────────────────────────────────────────────
    _is_local = DEPLOYMENT_MODE == 'local'
    _is_coolify = DEPLOYMENT_MODE == 'coolify'
    _db_host = _hostname_from_url(SQLALCHEMY_DATABASE_URI)
    _redis_host = _hostname_from_url(REDIS_URL) if REDIS_URL else None
    _minio_host = (MINIO_ENDPOINT or '').split(':')[0].strip() if MINIO_ENDPOINT else None

    if _is_local:
        _coolify_hosts = {'db', 'redis', 'minio'}
        _local_problems: list[str] = []
        if _db_host in _coolify_hosts:
            _local_problems.append(
                f"DATABASE_URL host '{_db_host}' — use localhost or 127.0.0.1 "
                f"when DEPLOYMENT_MODE=local."
            )
        if _redis_host in _coolify_hosts:
            _local_problems.append(
                f"REDIS_URL host '{_redis_host}' — use localhost "
                f"when DEPLOYMENT_MODE=local."
            )
        if _minio_host in _coolify_hosts:
            _local_problems.append(
                f"MINIO_ENDPOINT host '{_minio_host}' — use localhost "
                f"when DEPLOYMENT_MODE=local."
            )
        if _local_problems:
            raise ValueError(
                "DEPLOYMENT_MODE=local but Coolify/Docker hostnames detected:\n"
                + "\n".join(f"  - {p}" for p in _local_problems)
            )

    if _is_coolify:
        _prod_problems: list[str] = []
        if _db_host in ('localhost', '127.0.0.1'):
            _prod_problems.append(
                f"DATABASE_URL host '{_db_host}' — use the Coolify service "
                f"hostname 'db' when DEPLOYMENT_MODE=coolify."
            )
        if _redis_host in ('localhost', '127.0.0.1'):
            _prod_problems.append(
                f"REDIS_URL host '{_redis_host}' — use the Coolify service "
                f"hostname 'redis' when DEPLOYMENT_MODE=coolify."
            )
        if _minio_host in ('localhost', '127.0.0.1'):
            _prod_problems.append(
                f"MINIO_ENDPOINT host '{_minio_host}' — use the Coolify service "
                f"hostname 'minio' when DEPLOYMENT_MODE=coolify."
            )
        if _as_bool(os.environ.get('FLASK_DEBUG')):
            _prod_problems.append(
                "FLASK_DEBUG=1 — must be 0 in production/Coolify."
            )
        if _prod_problems:
            raise ValueError(
                "DEPLOYMENT_MODE=coolify but local/development values detected:\n"
                + "\n".join(f"  - {p}" for p in _prod_problems)
            )
