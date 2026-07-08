from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_client
from app.models import LLMUsageRecord
from app.observability import log_event, mask_phone
from app.settings import Settings, get_settings

DEFAULT_LOGIN_RATE_LIMIT_PER_MINUTE = 600
DEFAULT_AUTH_PHONE_RATE_LIMIT_PER_HOUR = 600
DEFAULT_ANSWER_SUBMIT_RATE_LIMIT_PER_MINUTE = 600
DEFAULT_LLM_DAILY_TOKEN_QUOTA = 1_000_000
DEFAULT_LLM_MONTHLY_TOKEN_QUOTA = 10_000_000
DEFAULT_LLM_DAILY_CALL_QUOTA = 1_000


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    limit: int
    remaining: int
    retry_after_seconds: int
    window_seconds: int
    scope: str


@dataclass(frozen=True)
class RateLimitBackendUnavailable(Exception):
    scope: str
    backend: str
    retry_after_seconds: int = 1


@dataclass(frozen=True)
class QuotaExceeded(Exception):
    quota_name: str
    limit: int
    current_usage: int
    requested: int


_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limit_state() -> None:
    _rate_limit_buckets.clear()


def client_ip(request: Request | None) -> str:
    if request is None or request.client is None:
        return "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or request.client.host
    return request.client.host


def build_rate_limit_key(*parts: Any) -> str:
    normalized = [str(part).strip().lower() for part in parts if part is not None and str(part).strip()]
    return ":".join(normalized) or "unknown"


class MemoryRateLimiterBackend:
    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        scope: str,
        now: float | None = None,
    ) -> None:
        current = now if now is not None else datetime.now(timezone.utc).timestamp()
        bucket = _rate_limit_buckets[key]
        cutoff = current - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - current) + 1)
            log_event(
                "rate_limit_exceeded",
                status="denied",
                backend="memory",
                scope=scope,
                limit=limit,
                window_seconds=window_seconds,
                retry_after_seconds=retry_after,
            )
            raise RateLimitExceeded(
                limit=limit,
                remaining=0,
                retry_after_seconds=retry_after,
                window_seconds=window_seconds,
                scope=scope,
            )

        bucket.append(current)


class RedisRateLimiterBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _redis_key(self, key: str, scope: str) -> str:
        prefix = getattr(self.settings, "redis_rate_limit_prefix", "interview-agent:rate-limit").strip().rstrip(":")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{prefix}:{scope}:{digest}"

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        scope: str,
        now: float | None = None,
    ) -> None:
        del now
        client = redis_client.get_redis_client(self.settings)
        redis_key = self._redis_key(key, scope)
        count = int(client.incr(redis_key))
        if count == 1:
            client.expire(redis_key, window_seconds)
        ttl = int(client.ttl(redis_key))
        if ttl < 0:
            client.expire(redis_key, window_seconds)
            ttl = window_seconds

        if count > limit:
            retry_after = max(1, ttl)
            log_event(
                "rate_limit_exceeded",
                status="denied",
                backend="redis",
                scope=scope,
                limit=limit,
                window_seconds=window_seconds,
                retry_after_seconds=retry_after,
            )
            raise RateLimitExceeded(
                limit=limit,
                remaining=0,
                retry_after_seconds=retry_after,
                window_seconds=window_seconds,
                scope=scope,
            )


def _rate_limit_backend_name(settings: Settings) -> str:
    normalized = getattr(settings, "normalized_rate_limit_backend", None)
    if isinstance(normalized, str):
        return normalized
    return str(getattr(settings, "rate_limit_backend", "memory")).strip().lower() or "memory"


def _is_production(settings: Settings) -> bool:
    return bool(getattr(settings, "is_production", False))


def _check_memory_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int,
    scope: str,
    now: float | None = None,
) -> None:
    MemoryRateLimiterBackend().check(key, limit=limit, window_seconds=window_seconds, scope=scope, now=now)


def check_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int,
    scope: str,
    settings: Settings | None = None,
    now: float | None = None,
) -> None:
    active_settings = settings or get_settings()
    if not getattr(active_settings, "rate_limit_enabled", True):
        return

    backend_name = _rate_limit_backend_name(active_settings)
    if backend_name == "redis":
        try:
            RedisRateLimiterBackend(active_settings).check(
                key,
                limit=limit,
                window_seconds=window_seconds,
                scope=scope,
                now=now,
            )
            return
        except RedisError as exc:
            log_event(
                "rate_limit_backend_unavailable",
                status="error",
                backend="redis",
                scope=scope,
                error_type=exc.__class__.__name__,
            )
            if _is_production(active_settings):
                raise RateLimitBackendUnavailable(scope=scope, backend="redis") from exc
            log_event("rate_limit_backend_fallback", status="warning", backend="memory", failed_backend="redis", scope=scope)

    _check_memory_rate_limit(key, limit=limit, window_seconds=window_seconds, scope=scope, now=now)


def rate_limit_http_exception(exc: RateLimitExceeded | RateLimitBackendUnavailable | QuotaExceeded) -> HTTPException:
    if isinstance(exc, RateLimitExceeded):
        detail = {
            "message": "Too many requests",
            "scope": exc.scope,
            "retry_after_seconds": exc.retry_after_seconds,
        }
        headers = {
            "Retry-After": str(exc.retry_after_seconds),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": str(exc.remaining),
        }
        return HTTPException(status_code=429, detail=detail, headers=headers)

    if isinstance(exc, RateLimitBackendUnavailable):
        detail = {
            "message": "Rate limit backend unavailable",
            "scope": exc.scope,
            "backend": exc.backend,
            "retry_after_seconds": exc.retry_after_seconds,
        }
        return HTTPException(status_code=503, detail=detail, headers={"Retry-After": str(exc.retry_after_seconds)})

    detail = {
        "message": "Quota exceeded",
        "quota": exc.quota_name,
        "limit": exc.limit,
        "current_usage": exc.current_usage,
        "requested": exc.requested,
    }
    return HTTPException(status_code=429, detail=detail)


def check_auth_rate_limits(request: Request | None, phone: str, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    ip = client_ip(request)
    check_rate_limit(
        build_rate_limit_key("auth", "ip", ip),
        limit=getattr(active_settings, "login_rate_limit_per_minute", DEFAULT_LOGIN_RATE_LIMIT_PER_MINUTE),
        window_seconds=60,
        scope="auth_ip_per_minute",
        settings=active_settings,
    )
    try:
        check_rate_limit(
            build_rate_limit_key("auth", "phone", phone),
            limit=getattr(active_settings, "auth_phone_rate_limit_per_hour", DEFAULT_AUTH_PHONE_RATE_LIMIT_PER_HOUR),
            window_seconds=3600,
            scope="auth_phone_per_hour",
            settings=active_settings,
        )
    except RateLimitExceeded:
        log_event("rate_limit_phone_denied", status="denied", phone=mask_phone(phone))
        raise


def check_answer_submit_rate_limit(user_id: int, session_id: int, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    check_rate_limit(
        build_rate_limit_key("answer", "user", user_id, "session", session_id),
        limit=getattr(active_settings, "answer_submit_rate_limit_per_minute", DEFAULT_ANSWER_SUBMIT_RATE_LIMIT_PER_MINUTE),
        window_seconds=60,
        scope="answer_submit_per_minute",
        settings=active_settings,
    )


def _day_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _token_usage_since(db: AsyncSession, user_id: int, since: datetime) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0)).where(
            LLMUsageRecord.user_id == user_id,
            LLMUsageRecord.created_at >= since,
        )
    )
    return int(result.scalar_one() or 0)


async def _call_count_since(db: AsyncSession, user_id: int, since: datetime) -> int:
    result = await db.execute(
        select(func.count()).select_from(LLMUsageRecord).where(
            LLMUsageRecord.user_id == user_id,
            LLMUsageRecord.created_at >= since,
        )
    )
    return int(result.scalar_one() or 0)


async def check_user_llm_quota(
    db: AsyncSession,
    *,
    user_id: int,
    estimated_tokens: int,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> None:
    active_settings = settings or get_settings()
    if not getattr(active_settings, "rate_limit_enabled", True):
        return

    requested = max(estimated_tokens, 0)
    day_start = _day_start_utc(now)
    month_start = _month_start_utc(now)
    daily_tokens = await _token_usage_since(db, user_id, day_start)
    monthly_tokens = await _token_usage_since(db, user_id, month_start)
    daily_calls = await _call_count_since(db, user_id, day_start)

    daily_call_quota = getattr(active_settings, "llm_daily_call_quota", DEFAULT_LLM_DAILY_CALL_QUOTA)
    daily_token_quota = getattr(active_settings, "llm_daily_token_quota", DEFAULT_LLM_DAILY_TOKEN_QUOTA)
    monthly_token_quota = getattr(active_settings, "llm_monthly_token_quota", DEFAULT_LLM_MONTHLY_TOKEN_QUOTA)
    if daily_calls >= daily_call_quota:
        raise QuotaExceeded("llm_daily_call_quota", daily_call_quota, daily_calls, 1)
    if daily_tokens + requested > daily_token_quota:
        raise QuotaExceeded("llm_daily_token_quota", daily_token_quota, daily_tokens, requested)
    if monthly_tokens + requested > monthly_token_quota:
        raise QuotaExceeded("llm_monthly_token_quota", monthly_token_quota, monthly_tokens, requested)
