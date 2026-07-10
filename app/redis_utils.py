import os
from typing import Mapping, Optional
from urllib.parse import quote, urlparse

import redis

_REDIS_PROBE_TIMEOUT = 2

# Module-level client populated by init_redis(). Importable from a single
# stable place: `from app.redis_utils import redis_client`.
redis_client: Optional[redis.Redis] = None


def build_redis_url_from_env(env: Mapping[str, str] | None = None) -> str:
    """Build the Redis URL from the environment.

    Canonical variable: REDIS_URL.
    Legacy fallback: REDIS_HOST / REDIS_PORT / REDIS_DB / REDIS_PASSWORD
    (kept for backward compatibility but not documented as canonical).

    If nothing is set, returns an empty string so init_redis() can mark
    Redis as unavailable and degrade gracefully.
    """
    source = env or os.environ

    redis_url = (source.get("REDIS_URL") or "").strip()
    if redis_url:
        return redis_url

    # Legacy fallback for projects that still use individual Redis vars.
    redis_host = (source.get("REDIS_HOST") or "").strip()
    if redis_host:
        port = (source.get("REDIS_PORT") or "6379").strip()
        db = (source.get("REDIS_DB") or "0").strip()
        password = source.get("REDIS_PASSWORD")
        if password:
            encoded = quote(password, safe="")
            return f"redis://:{encoded}@{redis_host}:{port}/{db}"
        return f"redis://{redis_host}:{port}/{db}"

    return ""


def _redis_hostname(redis_url: str | None) -> str | None:
    if not redis_url:
        return None
    try:
        return urlparse(redis_url).hostname
    except Exception:
        return None


def is_redis_available(
    redis_url: str | None,
    timeout_seconds: int = _REDIS_PROBE_TIMEOUT,
) -> tuple[bool, str | None]:
    if not redis_url:
        return False, "Redis URL vacía"

    try:
        client = redis.from_url(
            redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
        )
        client.ping()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _safe_log_url(redis_url: str) -> str:
    """Strip credentials from a Redis URL before writing it to logs."""
    try:
        parsed = redis.connection.parse_url(redis_url)
        host = parsed.get("host") or "localhost"
        port = parsed.get("port") or 6379
        db = parsed.get("db", 0)
        return f"redis://{host}:{port}/{db}"
    except Exception:
        return "redis://<invalid-url>"


def init_redis(app) -> bool:
    """
    Intenta conectar a Redis usando REDIS_URL de la configuración de la app.
    Si falla, loguea un WARNING y deja REDIS_AVAILABLE = False.
    Nunca lanza excepciones: es seguro llamar en create_app().
    """
    global redis_client
    redis_url = (app.config.get('REDIS_URL') or '').strip()

    if not redis_url:
        app.logger.warning(
            "REDIS_URL no configurada. Redis no estará disponible."
        )
        app.config['REDIS_AVAILABLE'] = False
        redis_client = None
        return False

    if (app.config.get('ENV_NAME') or '').strip().lower() == 'development':
        redis_host = _redis_hostname(redis_url)
        if redis_host == 'redis':
            app.logger.warning(
                "Your local REDIS_URL points to host 'redis' and only works "
                "inside Docker/Coolify. For local venv development, use "
                "redis://localhost:6379/0 or leave REDIS_URL unset."
            )
            app.config['REDIS_AVAILABLE'] = False
            redis_client = None
            return False

    try:
        client = redis.from_url(
            redis_url,
            socket_connect_timeout=_REDIS_PROBE_TIMEOUT,
            socket_timeout=_REDIS_PROBE_TIMEOUT,
        )
        client.ping()
        app.config['REDIS_AVAILABLE'] = True
        redis_client = client
        app.logger.info(f"Redis disponible en: {_safe_log_url(redis_url)}")
        return True
    except Exception as exc:
        app.config['REDIS_AVAILABLE'] = False
        redis_client = None
        app.logger.warning(
            f"Redis no disponible ({_safe_log_url(redis_url)}): {exc}. "
            "Rate limiting usando memoria local."
        )
        return False


def check_redis_connection() -> bool:
    """
    Helper de diagnóstico: devuelve True si Redis responde a PING.
    Usar solo en health checks o diagnósticos puntuales; no llamar por request.
    """
    try:
        if redis_client is None:
            return False
        redis_client.ping()
        return True
    except Exception:
        return False
