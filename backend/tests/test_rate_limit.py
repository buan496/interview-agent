from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import sessions as sessions_api
from app.core.interviewer import EvaluationResult as EngineEvaluationResult
from app.core.interviewer import Verdict
from app.db import get_db
from app.main import app
from app.models import Base, Company, LLMUsageRecord, Position, Question, QuestionTag, Tag, User
from app.rate_limit import (
    RateLimitBackendUnavailable,
    RateLimitExceeded,
    build_rate_limit_key,
    check_rate_limit,
    rate_limit_http_exception,
    reset_rate_limit_state,
)


class FakeRateLimitInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-rate-limit-model"})()
        self.last_llm_call_attempted = True
        self.last_llm_call_failed = False
        self.last_llm_error_type = None

    async def evaluate_answer(self, *_args, **_kwargs) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            coverage=0.86,
            correct_points=["Mentioned memory access"],
            missing_points=[],
            wrong_points=[],
            action="verdict",
            verdict=Verdict(
                score=86,
                mastery="strong",
                feedback="Answer is clear.",
                ideal_answer="Cover memory access, event loop, IO multiplexing, and optimized data structures.",
            ),
        )


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "environment": "development",
        "is_production": False,
        "auth_dev_code_enabled": True,
        "auth_dev_code": "000000",
        "sms_provider_key": "",
        "jwt_secret": "rate-limit-test-secret",
        "access_token_expire_minutes": 60,
        "admin_phone_set": set(),
        "rate_limit_enabled": True,
        "rate_limit_backend": "memory",
        "redis_url": "redis://localhost:6379/0",
        "redis_rate_limit_prefix": "test:rate-limit",
        "login_rate_limit_per_minute": 100,
        "auth_phone_rate_limit_per_hour": 100,
        "answer_submit_rate_limit_per_minute": 100,
        "llm_daily_token_quota": 1_000_000,
        "llm_monthly_token_quota": 10_000_000,
        "llm_daily_call_quota": 1_000,
        "llm_usage_metering_enabled": True,
        "llm_pricing_version": "llm-pricing-v1-test",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.keys: list[str] = []

    def incr(self, key: str) -> int:
        self.keys.append(key)
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True

    def ttl(self, key: str) -> int:
        return self.expirations.get(key, -1)


class BrokenRedis:
    def incr(self, _key: str) -> int:
        raise RedisConnectionError("redis unavailable")


class RateLimitTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 10
        reset_rate_limit_state()
        self.engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._seed_question()

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            async with self.sessionmaker() as session:
                yield session

        self.original_session_local = sessions_api.SessionLocal
        sessions_api.SessionLocal = self.sessionmaker
        app.dependency_overrides[get_db] = override_get_db
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        sessions_api.SessionLocal = self.original_session_local
        reset_rate_limit_state()
        await self.engine.dispose()

    async def _seed_question(self) -> None:
        async with self.sessionmaker() as db:
            company = Company(id=1, name="General Co", region="CN", tier=1)
            position = Position(id=1, name="Backend Engineer")
            tag = Tag(id=7, name="Redis", category="knowledge")
            question = Question(
                id=100,
                title="Why is Redis fast?",
                answer_key="Cover memory access, event loop, IO multiplexing, and optimized data structures.",
                difficulty=3,
                qtype="knowledge",
                source_type="seed",
                company_id=company.id,
                position_id=position.id,
                status="active",
            )
            db.add_all([company, position, tag, question])
            await db.flush()
            db.add(QuestionTag(question_id=question.id, tag_id=tag.id))
            await db.commit()

    async def _auth_headers(self, phone: str, settings: SimpleNamespace | None = None) -> tuple[dict[str, str], int]:
        if settings is None:
            response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        else:
            with patch("app.api.auth.get_settings", return_value=settings):
                response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        async with self.sessionmaker() as db:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}, user.id

    async def _create_single_session(self, headers: dict[str, str]) -> tuple[int, int]:
        response = await self.client.post(
            "/api/sessions",
            headers=headers,
            json={"mode": "single", "question_id": 100},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["session_id"], payload["first_question"]["sq_id"]

    async def test_login_ip_rate_limit_returns_429_with_request_id(self) -> None:
        settings = _settings(login_rate_limit_per_minute=1, auth_phone_rate_limit_per_hour=100)

        with patch("app.api.auth.get_settings", return_value=settings):
            first = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000001", "code": "123456"},
                headers={"X-Request-ID": "login-first"},
            )
            second = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000002", "code": "123456"},
                headers={"X-Request-ID": "login-limited"},
            )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["request_id"], "login-limited")
        self.assertGreaterEqual(int(second.headers["Retry-After"]), 1)
        self.assertNotIn("123456", second.text)

    async def test_phone_hourly_rate_limit_returns_429_without_leaking_code(self) -> None:
        settings = _settings(login_rate_limit_per_minute=100, auth_phone_rate_limit_per_hour=1)

        with patch("app.api.auth.get_settings", return_value=settings):
            first = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000003", "code": "123456"},
                headers={"X-Request-ID": "phone-first"},
            )
            second = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000003", "code": "654321"},
                headers={"X-Request-ID": "phone-limited"},
            )

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["request_id"], "phone-limited")
        self.assertNotIn("654321", second.text)
        self.assertNotIn("18800000003", second.text)

    async def test_redis_backend_sets_ttl_and_returns_429_headers(self) -> None:
        fake_redis = FakeRedis()
        settings = _settings(rate_limit_backend="redis", redis_rate_limit_prefix="test:rl")
        raw_key = build_rate_limit_key("auth", "phone", "18800000030")

        with patch("app.rate_limit.redis_client.get_redis_client", return_value=fake_redis):
            check_rate_limit(raw_key, limit=1, window_seconds=60, scope="auth_phone_per_hour", settings=settings)
            with self.assertRaises(RateLimitExceeded) as ctx:
                check_rate_limit(raw_key, limit=1, window_seconds=60, scope="auth_phone_per_hour", settings=settings)

        self.assertEqual(list(fake_redis.expirations.values()), [60])
        self.assertTrue(fake_redis.keys)
        self.assertNotIn("18800000030", fake_redis.keys[0])
        response = rate_limit_http_exception(ctx.exception)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertEqual(response.headers["X-RateLimit-Limit"], "1")
        self.assertEqual(response.headers["X-RateLimit-Remaining"], "0")

    async def test_redis_backend_fails_closed_in_production_when_unavailable(self) -> None:
        settings = _settings(environment="production", is_production=True, rate_limit_backend="redis")

        with patch("app.rate_limit.redis_client.get_redis_client", return_value=BrokenRedis()):
            with self.assertRaises(RateLimitBackendUnavailable) as ctx:
                check_rate_limit("auth:ip:127.0.0.1", limit=1, window_seconds=60, scope="auth_ip_per_minute", settings=settings)

        response = rate_limit_http_exception(ctx.exception)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "1")
        self.assertEqual(response.detail["backend"], "redis")

    async def test_redis_backend_falls_back_to_memory_outside_production(self) -> None:
        settings = _settings(rate_limit_backend="redis")

        with patch("app.rate_limit.redis_client.get_redis_client", return_value=BrokenRedis()):
            check_rate_limit("answer:user:1:session:1", limit=1, window_seconds=60, scope="answer_submit_per_minute", settings=settings)
            with self.assertRaises(RateLimitExceeded):
                check_rate_limit("answer:user:1:session:1", limit=1, window_seconds=60, scope="answer_submit_per_minute", settings=settings)

    async def test_answer_submit_rate_limit_returns_429(self) -> None:
        headers, _ = await self._auth_headers("18800000004")
        session_id, sq_id = await self._create_single_session(headers)
        settings = _settings(answer_submit_rate_limit_per_minute=1)

        with (
            patch("app.rate_limit.get_settings", return_value=settings),
            patch.object(sessions_api, "InterviewerEngine", FakeRateLimitInterviewerEngine),
        ):
            async with self.client.stream(
                "POST",
                f"/api/sessions/{session_id}/answer",
                headers={**headers, "X-Request-ID": "answer-first"},
                json={"sq_id": sq_id, "content": "Redis is fast because it stores data in memory."},
            ) as first:
                self.assertEqual(first.status_code, 200)
                await first.aread()
            second = await self.client.post(
                f"/api/sessions/{session_id}/answer",
                headers={**headers, "X-Request-ID": "answer-limited"},
                json={"sq_id": sq_id, "content": "This answer should be rate limited."},
            )

        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["request_id"], "answer-limited")
        self.assertNotIn("This answer should be rate limited", second.text)

    async def test_llm_quota_is_current_user_scoped(self) -> None:
        user_a_headers, user_a_id = await self._auth_headers("18800000005")
        user_b_headers, _ = await self._auth_headers("18800000006")
        session_a_id, sq_a_id = await self._create_single_session(user_a_headers)
        session_b_id, sq_b_id = await self._create_single_session(user_b_headers)

        async with self.sessionmaker() as db:
            db.add(
                LLMUsageRecord(
                    user_id=user_a_id,
                    session_id=session_a_id,
                    request_id="existing-usage",
                    feature="scoring",
                    provider="mock",
                    model="local-fallback",
                    prompt_tokens=990,
                    completion_tokens=0,
                    total_tokens=990,
                    estimated_cost=0,
                    currency="USD",
                    pricing_version="llm-pricing-v1-test",
                    latency_ms=10,
                    status="success",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

        settings = _settings(llm_daily_token_quota=1_000, llm_monthly_token_quota=10_000, llm_daily_call_quota=100)
        with (
            patch("app.rate_limit.get_settings", return_value=settings),
            patch.object(sessions_api, "InterviewerEngine", FakeRateLimitInterviewerEngine),
        ):
            limited = await self.client.post(
                f"/api/sessions/{session_a_id}/answer",
                headers={**user_a_headers, "X-Request-ID": "quota-limited"},
                json={"sq_id": sq_a_id, "content": "Redis is fast because it stores data in memory."},
            )
            async with self.client.stream(
                "POST",
                f"/api/sessions/{session_b_id}/answer",
                headers={**user_b_headers, "X-Request-ID": "quota-user-b"},
                json={"sq_id": sq_b_id, "content": "Redis is fast because it stores data in memory."},
            ) as allowed:
                self.assertEqual(allowed.status_code, 200)
                stream_text = await allowed.aread()

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["request_id"], "quota-limited")
        self.assertEqual(limited.json()["detail"]["quota"], "llm_daily_token_quota")
        self.assertIn(b"event: done", stream_text)


if __name__ == "__main__":
    unittest.main()
