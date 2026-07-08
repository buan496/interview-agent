from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from redis import Redis

from app.settings import Settings, get_settings

_redis_client: Redis | None = None


def mask_redis_url(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<invalid-url>"
    if not parsed.password:
        return value
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:****@{host}{port}" if username else f"****@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def get_redis_client(settings: Settings | None = None) -> Redis:
    global _redis_client
    active_settings = settings or get_settings()
    if _redis_client is None:
        _redis_client = Redis.from_url(
            active_settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=active_settings.redis_connect_timeout_seconds,
            socket_timeout=active_settings.redis_socket_timeout_seconds,
        )
    return _redis_client


def ping_redis(settings: Settings | None = None) -> bool:
    return bool(get_redis_client(settings).ping())


def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
