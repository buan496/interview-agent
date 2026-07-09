from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.async_jobs import (
    JOB_TYPE_MEMORY_REFRESH,
    RedisAsyncJobQueueBackend,
    create_async_job,
    reset_async_job_queue_state,
    run_job_once,
)
from app.db import get_db
from app.main import app
from app.metrics import metrics_content
from app.models import AsyncJob, AuditEvent, Base
from app.settings import Settings


class _FakeRedis:
    def __init__(self) -> None:
        self.items: list[str] = []

    def rpush(self, _queue_name: str, value: str) -> None:
        self.items.append(value)

    def lpop(self, _queue_name: str) -> str | None:
        if not self.items:
            return None
        return self.items.pop(0)


class AsyncJobsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 10
        reset_async_job_queue_state()
        self.engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            async with self.sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        reset_async_job_queue_state()
        await self.engine.dispose()

    async def _auth_headers(self, phone: str = "18800007000") -> dict[str, str]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def test_user_can_create_and_read_memory_refresh_async_job(self) -> None:
        headers = await self._auth_headers()

        created = await self.client.post("/api/me/memories/refresh-async", headers=headers)
        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["job"]["job_type"], "memory_refresh")
        self.assertEqual(payload["job"]["payload_json"]["trigger"], "manual_async")

        detail = await self.client.get(f"/api/me/jobs/{payload['job_id']}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], payload["job_id"])

        listed = await self.client.get("/api/me/jobs", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)

        async with self.sessionmaker() as db:
            event = (
                await db.execute(select(AuditEvent).where(AuditEvent.action == "async_job_created"))
            ).scalar_one_or_none()
            self.assertIsNotNone(event)

        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_async_jobs_created_total{job_type="memory_refresh"}', metrics)

    async def test_user_cannot_read_other_users_job(self) -> None:
        user_a = await self._auth_headers("18800007001")
        user_b = await self._auth_headers("18800007002")

        created = await self.client.post("/api/me/memories/refresh-async", headers=user_b)
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["job_id"]

        denied = await self.client.get(f"/api/me/jobs/{job_id}", headers=user_a)
        self.assertEqual(denied.status_code, 404)

        listed = await self.client.get("/api/me/jobs", headers=user_a)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 0)

    async def test_worker_runs_memory_refresh_job_successfully(self) -> None:
        headers = await self._auth_headers()
        response = await self.client.post("/api/me/memories/refresh-async", headers=headers)
        job_id = int(response.json()["job_id"])

        async with self.sessionmaker() as db:
            result = await run_job_once(db, settings=Settings(async_job_backend="memory"))
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "succeeded")
            job = await db.get(AsyncJob, job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "succeeded")
            self.assertEqual(job.attempts, 1)
            self.assertEqual(job.result_json["total_active"], 0)

        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_async_jobs_completed_total{job_type="memory_refresh",status="succeeded"}', metrics)
        self.assertIn("interview_agent_async_job_duration_seconds", metrics)

    async def test_worker_marks_failed_after_max_attempts(self) -> None:
        headers = await self._auth_headers()
        response = await self.client.post("/api/me/memories/refresh-async", headers=headers)
        job_id = int(response.json()["job_id"])

        async with self.sessionmaker() as db:
            job = await db.get(AsyncJob, job_id)
            job.max_attempts = 1
            await db.commit()

            with patch("app.async_jobs.refresh_user_memories", side_effect=RuntimeError("memory failed")):
                result = await run_job_once(db, settings=Settings(async_job_backend="memory", async_job_max_attempts=1))

            self.assertIsNotNone(result)
            self.assertEqual(result.status, "failed")
            failed = await db.get(AsyncJob, job_id)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.attempts, 1)
            self.assertEqual(failed.error_type, "RuntimeError")
            self.assertNotIn("answer", str(failed.payload_json).lower())

            event = (
                await db.execute(select(AuditEvent).where(AuditEvent.action == "async_job_failed"))
            ).scalar_one_or_none()
            self.assertIsNotNone(event)

    async def test_job_payload_sanitizes_sensitive_fields(self) -> None:
        headers = await self._auth_headers()
        await self.client.post("/api/me/memories/refresh-async", headers=headers)

        async with self.sessionmaker() as db:
            job = await create_async_job(
                db,
                job_type=JOB_TYPE_MEMORY_REFRESH,
                user_id=1,
                payload={"user_id": 1, "trigger": "manual", "answer_text": "private answer", "token": "secret-token"},
                enqueue=False,
            )
            self.assertEqual(job.payload_json["answer_text"], "<redacted>")
            self.assertEqual(job.payload_json["token"], "<redacted>")

    async def test_redis_queue_backend_enqueues_and_dequeues_job_ids(self) -> None:
        fake = _FakeRedis()
        settings = Settings(async_job_backend="redis", async_job_queue_name="test-queue")
        with patch("app.redis_client.get_redis_client", return_value=fake):
            backend = RedisAsyncJobQueueBackend(settings)
            backend.enqueue(42)
            self.assertEqual(backend.dequeue(), 42)
            self.assertIsNone(backend.dequeue())

    async def test_sync_memory_refresh_api_still_works(self) -> None:
        headers = await self._auth_headers()
        response = await self.client.post("/api/me/memories/refresh", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_active"], 0)


if __name__ == "__main__":
    unittest.main()
