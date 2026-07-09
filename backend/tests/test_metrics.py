from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.llm_usage import record_llm_usage
from app.main import app
from app.metrics import metrics_content
from app.models import Base, Session, User
from app.rate_limit import RateLimitExceeded, QuotaExceeded, rate_limit_http_exception


class _ReadyDb:
    async def execute(self, _stmt):
        return None


class MetricsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_metrics_endpoint_returns_prometheus_text(self) -> None:
        response = await self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        self.assertIn("interview_agent_http_requests_total", response.text)

    async def test_http_request_counter_increases_and_uses_normalized_route(self) -> None:
        await self.client.get("/health")
        metrics = (await self.client.get("/metrics")).text

        self.assertIn('interview_agent_http_requests_total{method="GET",route="/health",status_class="2xx"}', metrics)
        self.assertNotIn("request_id", metrics)

    async def test_metrics_do_not_expose_authorization_phone_or_request_id(self) -> None:
        token = "secret-token-that-must-not-appear"
        request_id = "metrics-sensitive-request"
        phone = "18800009999"
        await self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}", "X-Request-ID": request_id},
        )

        metrics = (await self.client.get("/metrics")).text

        self.assertNotIn(token, metrics)
        self.assertNotIn(request_id, metrics)
        self.assertNotIn(phone, metrics)
        self.assertNotIn("user_id", metrics)

    async def test_metrics_can_be_disabled_by_config(self) -> None:
        disabled_settings = SimpleNamespace(metrics_enabled=False, is_production=False, metrics_protect_in_production=True)

        with patch("app.main.settings", disabled_settings):
            response = await self.client.get("/metrics")

        self.assertEqual(response.status_code, 404)

    async def test_ready_updates_dependency_gauges(self) -> None:
        async def override_get_db() -> AsyncIterator[_ReadyDb]:
            yield _ReadyDb()

        app.dependency_overrides[get_db] = override_get_db

        response = await self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        metrics = (await self.client.get("/metrics")).text

        self.assertIn('interview_agent_dependency_ready{dependency="db"} 1.0', metrics)
        self.assertIn('interview_agent_dependency_ready{dependency="redis"} 1.0', metrics)

    async def test_rate_limit_and_quota_metrics_are_recorded(self) -> None:
        rate_limit_exc = RateLimitExceeded(
            limit=1,
            remaining=0,
            retry_after_seconds=60,
            window_seconds=60,
            scope="auth_ip_per_minute",
        )
        quota_exc = QuotaExceeded(
            quota_name="llm_daily_token_quota",
            limit=100,
            current_usage=100,
            requested=1,
        )

        self.assertEqual(rate_limit_http_exception(rate_limit_exc).status_code, 429)
        self.assertEqual(rate_limit_http_exception(quota_exc).status_code, 429)
        metrics = metrics_content().decode("utf-8")

        self.assertIn('interview_agent_rate_limit_exceeded_total{scope="login_ip"}', metrics)
        self.assertIn('interview_agent_quota_exceeded_total{quota_type="daily_tokens"}', metrics)

    async def test_llm_usage_metrics_are_recorded_without_text_payload(self) -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        try:
            async with sessionmaker() as db:
                user = User(id=9001, phone="18800008888")
                db.add(user)
                db.add(Session(id=9002, user_id=user.id, mode="single", status="ongoing", started_at=datetime.now(timezone.utc), total_questions=1))
                await db.flush()
                await record_llm_usage(
                    db,
                    user_id=user.id,
                    session_id=9002,
                    request_id="llm-metrics-request",
                    feature="scoring",
                    provider="mock",
                    model="local-fallback",
                    prompt_tokens=12,
                    completion_tokens=5,
                    latency_ms=25,
                    status="success",
                )
                await db.commit()
        finally:
            await engine.dispose()

        metrics = metrics_content().decode("utf-8")

        self.assertIn('interview_agent_llm_calls_total{feature="scoring",model="local-fallback",provider="mock",status="success"}', metrics)
        self.assertIn('interview_agent_llm_tokens_total{feature="scoring",model="local-fallback",provider="mock",token_type="prompt"}', metrics)
        self.assertIn('interview_agent_llm_tokens_total{feature="scoring",model="local-fallback",provider="mock",token_type="total"}', metrics)
        self.assertIn('interview_agent_llm_estimated_cost_total{currency="usd",feature="scoring",model="local-fallback",provider="mock"}', metrics)
        self.assertNotIn("llm-metrics-request", metrics)
        self.assertNotIn("18800008888", metrics)


if __name__ == "__main__":
    unittest.main()
