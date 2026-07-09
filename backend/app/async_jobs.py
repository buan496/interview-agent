from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal

from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_client
from app.audit import mask_audit_metadata
from app.memory import active_memory_count, refresh_user_memories
from app.metrics import (
    dec_async_job_in_progress,
    inc_async_job_in_progress,
    observe_async_job_duration,
    record_async_job_completed,
    record_async_job_created,
)
from app.models import AsyncJob, AuditEvent
from app.observability import get_request_id, log_event, log_exception
from app.settings import Settings, get_settings


JobType = Literal["memory_refresh", "report_generation", "question_import", "rubric_validation"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]

JOB_TYPE_MEMORY_REFRESH = "memory_refresh"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
SUPPORTED_JOB_TYPES = {JOB_TYPE_MEMORY_REFRESH}
SENSITIVE_PAYLOAD_KEYS = {
    "answer",
    "answer_text",
    "authorization",
    "code",
    "completion",
    "completion_text",
    "jwt",
    "password",
    "phone",
    "prompt",
    "prompt_text",
    "secret",
    "token",
    "verification_code",
}

_memory_queue: deque[str] = deque()


@dataclass(frozen=True)
class JobRunResult:
    job_id: int
    job_type: str
    status: str


class AsyncJobQueueBackend:
    def enqueue(self, job_id: int) -> None:
        raise NotImplementedError

    def dequeue(self) -> int | None:
        raise NotImplementedError


class MemoryAsyncJobQueueBackend(AsyncJobQueueBackend):
    def enqueue(self, job_id: int) -> None:
        _memory_queue.append(str(job_id))

    def dequeue(self) -> int | None:
        if not _memory_queue:
            return None
        return int(_memory_queue.popleft())


class RedisAsyncJobQueueBackend(AsyncJobQueueBackend):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def queue_name(self) -> str:
        return self.settings.async_job_queue_name.strip() or "interview-agent:async-jobs"

    def enqueue(self, job_id: int) -> None:
        redis_client.get_redis_client(self.settings).rpush(self.queue_name, str(job_id))

    def dequeue(self) -> int | None:
        value = redis_client.get_redis_client(self.settings).lpop(self.queue_name)
        if value is None:
            return None
        return int(value)


def reset_async_job_queue_state() -> None:
    _memory_queue.clear()


def get_queue_backend(settings: Settings | None = None) -> AsyncJobQueueBackend:
    active_settings = settings or get_settings()
    backend = active_settings.normalized_async_job_backend
    if backend == "redis":
        return RedisAsyncJobQueueBackend(active_settings)
    return MemoryAsyncJobQueueBackend()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_seconds(started_at: float) -> float:
    return max(0.0, perf_counter() - started_at)


def sanitize_job_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(sensitive in normalized_key for sensitive in SENSITIVE_PAYLOAD_KEYS):
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = sanitize_job_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_job_payload(item) for item in value[:50]]
    if isinstance(value, tuple):
        return [sanitize_job_payload(item) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def sanitize_error_message(exc: BaseException) -> str:
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()
    if any(key in lowered for key in SENSITIVE_PAYLOAD_KEYS):
        return "<redacted>"
    return message[:500]


def _add_job_audit_event(
    db: AsyncSession,
    *,
    job: AsyncJob,
    action: str,
    status: str,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=job.user_id,
            actor_role="user",
            action=action,
            resource_type="async_job",
            resource_id=str(job.id) if job.id is not None else None,
            target_user_id=job.user_id,
            request_id=get_request_id(),
            status=status,
            reason=reason,
            metadata_json=mask_audit_metadata(
                {
                    "job_type": job.job_type,
                    "job_status": job.status,
                    "attempts": job.attempts,
                    **dict(metadata or {}),
                }
            ),
        )
    )


async def create_async_job(
    db: AsyncSession,
    *,
    job_type: str,
    user_id: int,
    payload: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
    max_attempts: int | None = None,
    settings: Settings | None = None,
    enqueue: bool = True,
) -> AsyncJob:
    active_settings = settings or get_settings()
    if not active_settings.async_jobs_enabled:
        raise RuntimeError("Async jobs are disabled")
    if job_type not in SUPPORTED_JOB_TYPES:
        raise ValueError(f"Unsupported async job type: {job_type}")
    if idempotency_key:
        existing = (
            await db.execute(
                select(AsyncJob).where(
                    AsyncJob.user_id == user_id,
                    AsyncJob.job_type == job_type,
                    AsyncJob.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    sanitized_payload = sanitize_job_payload(payload or {})
    job = AsyncJob(
        job_type=job_type,
        user_id=user_id,
        status="queued",
        payload_json=dict(sanitized_payload),
        attempts=0,
        max_attempts=max_attempts or active_settings.async_job_max_attempts,
        idempotency_key=idempotency_key,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(job)
    await db.flush()
    _add_job_audit_event(db, job=job, action="async_job_created", status="success")
    await db.commit()
    await db.refresh(job)
    record_async_job_created(job.job_type)
    log_event("async_job.created", status="success", job_id=job.id, job_type=job.job_type, user_id=user_id)
    if enqueue:
        enqueue_job(job.id, settings=active_settings)
    return job


def enqueue_job(job_id: int, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    try:
        get_queue_backend(active_settings).enqueue(job_id)
        log_event("async_job.enqueued", status="success", job_id=job_id, backend=active_settings.normalized_async_job_backend)
    except RedisError as exc:
        log_exception("async_job.enqueue_failed", job_id=job_id, backend=active_settings.normalized_async_job_backend)
        if active_settings.is_production:
            raise
        MemoryAsyncJobQueueBackend().enqueue(job_id)
        log_event("async_job.enqueue_fallback", status="warning", job_id=job_id, backend="memory", error_type=exc.__class__.__name__)


def dequeue_job(settings: Settings | None = None) -> int | None:
    active_settings = settings or get_settings()
    try:
        return get_queue_backend(active_settings).dequeue()
    except RedisError as exc:
        log_exception("async_job.dequeue_failed", backend=active_settings.normalized_async_job_backend)
        if active_settings.is_production:
            raise
        log_event("async_job.dequeue_fallback", status="warning", backend="memory", error_type=exc.__class__.__name__)
        return MemoryAsyncJobQueueBackend().dequeue()


async def get_user_job(db: AsyncSession, *, user_id: int, job_id: int) -> AsyncJob | None:
    return (await db.execute(select(AsyncJob).where(AsyncJob.id == job_id, AsyncJob.user_id == user_id))).scalar_one_or_none()


async def list_user_jobs(
    db: AsyncSession,
    *,
    user_id: int,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AsyncJob], int]:
    conditions = [AsyncJob.user_id == user_id]
    if status:
        conditions.append(AsyncJob.status == status)
    if job_type:
        conditions.append(AsyncJob.job_type == job_type)
    total = int(await db.scalar(select(func.count()).select_from(AsyncJob).where(*conditions)) or 0)
    rows = (
        await db.execute(
            select(AsyncJob)
            .where(*conditions)
            .order_by(AsyncJob.created_at.desc(), AsyncJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def mark_job_running(db: AsyncSession, *, job_id: int) -> AsyncJob | None:
    job = (await db.execute(select(AsyncJob).where(AsyncJob.id == job_id))).scalar_one_or_none()
    if job is None or job.status != "queued":
        return None
    current = _now()
    job.status = "running"
    job.started_at = current
    job.updated_at = current
    job.attempts += 1
    await db.commit()
    await db.refresh(job)
    inc_async_job_in_progress(job.job_type)
    log_event("async_job.running", status="running", job_id=job.id, job_type=job.job_type, attempt=job.attempts)
    return job


async def mark_job_succeeded(db: AsyncSession, *, job_id: int, result: Mapping[str, Any] | None, duration_seconds: float) -> AsyncJob:
    job = (await db.execute(select(AsyncJob).where(AsyncJob.id == job_id))).scalar_one()
    current = _now()
    job.status = "succeeded"
    job.result_json = dict(sanitize_job_payload(result or {}))
    job.error_type = None
    job.error_message = None
    job.finished_at = current
    job.updated_at = current
    _add_job_audit_event(db, job=job, action="async_job_succeeded", status="success")
    await db.commit()
    await db.refresh(job)
    dec_async_job_in_progress(job.job_type)
    record_async_job_completed(job.job_type, "succeeded")
    observe_async_job_duration(job.job_type, duration_seconds)
    log_event("async_job.succeeded", status="success", job_id=job.id, job_type=job.job_type, attempts=job.attempts)
    return job


async def mark_job_failed(db: AsyncSession, *, job_id: int, exc: BaseException, duration_seconds: float, settings: Settings | None = None) -> AsyncJob:
    active_settings = settings or get_settings()
    job = (await db.execute(select(AsyncJob).where(AsyncJob.id == job_id))).scalar_one()
    current = _now()
    terminal = job.attempts >= job.max_attempts
    job.status = "failed" if terminal else "queued"
    job.error_type = exc.__class__.__name__
    job.error_message = sanitize_error_message(exc)
    job.finished_at = current if terminal else None
    job.updated_at = current
    action = "async_job_failed" if terminal else "async_job_retry_scheduled"
    _add_job_audit_event(db, job=job, action=action, status="failed" if terminal else "warning", reason=job.error_type)
    await db.commit()
    await db.refresh(job)
    dec_async_job_in_progress(job.job_type)
    observe_async_job_duration(job.job_type, duration_seconds)
    if terminal:
        record_async_job_completed(job.job_type, "failed")
        log_event("async_job.failed", status="failed", job_id=job.id, job_type=job.job_type, attempts=job.attempts, error_type=job.error_type)
    else:
        enqueue_job(job.id, settings=active_settings)
        log_event("async_job.retry_scheduled", status="warning", job_id=job.id, job_type=job.job_type, attempts=job.attempts, error_type=job.error_type)
    return job


async def _run_memory_refresh_job(db: AsyncSession, job: AsyncJob) -> dict[str, Any]:
    payload = job.payload_json or {}
    user_id = int(payload.get("user_id") or job.user_id)
    if user_id != job.user_id:
        raise ValueError("Job payload user_id does not match owner")
    trigger = str(payload.get("trigger") or "async")
    stats = await refresh_user_memories(db, user_id=job.user_id, trigger=trigger)
    total_active = await active_memory_count(db, job.user_id)
    return {"created": stats.created, "updated": stats.updated, "total_active": total_active}


async def dispatch_job(db: AsyncSession, job: AsyncJob) -> dict[str, Any]:
    if job.job_type == JOB_TYPE_MEMORY_REFRESH:
        return await _run_memory_refresh_job(db, job)
    raise ValueError(f"Unsupported async job type: {job.job_type}")


async def run_job_once(db: AsyncSession, *, job_id: int | None = None, settings: Settings | None = None) -> JobRunResult | None:
    active_settings = settings or get_settings()
    active_job_id = job_id if job_id is not None else dequeue_job(active_settings)
    if active_job_id is None:
        return None
    job = await mark_job_running(db, job_id=active_job_id)
    if job is None:
        return None
    started_at = perf_counter()
    try:
        result = await dispatch_job(db, job)
    except Exception as exc:
        log_exception("async_job.run_failed", job_id=active_job_id, job_type=job.job_type, error_type=exc.__class__.__name__)
        failed_job = await mark_job_failed(db, job_id=active_job_id, exc=exc, duration_seconds=_duration_seconds(started_at), settings=active_settings)
        return JobRunResult(job_id=failed_job.id, job_type=failed_job.job_type, status=failed_job.status)
    succeeded_job = await mark_job_succeeded(db, job_id=active_job_id, result=result, duration_seconds=_duration_seconds(started_at))
    return JobRunResult(job_id=succeeded_job.id, job_type=succeeded_job.job_type, status=succeeded_job.status)


async def worker_loop(*, settings: Settings | None = None, stop_after_one: bool = False) -> None:
    from app.db import SessionLocal

    active_settings = settings or get_settings()
    while True:
        async with SessionLocal() as db:
            await run_job_once(db, settings=active_settings)
        if stop_after_one:
            return
        await asyncio.sleep(active_settings.async_job_worker_poll_seconds)
