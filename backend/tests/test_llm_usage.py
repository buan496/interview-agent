from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
import unittest

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.llm_usage import (
    LLM_PRICING_VERSION,
    calculate_estimated_cost,
    get_user_usage_summary,
    record_llm_usage,
)
from app.main import app
from app.models import Base, LLMUsageRecord, Session, User


class LLMUsageTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 10
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
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def _auth_headers(self, phone: str) -> tuple[dict[str, str], int]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        async with self.sessionmaker() as db:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}, user.id

    async def test_cost_estimate_uses_pricing_version_and_handles_unknown_model(self) -> None:
        deepseek_cost = calculate_estimated_cost("deepseek", "deepseek-chat", 1000, 1000)
        unknown_cost = calculate_estimated_cost("unknown", "new-model", 1000, 1000)

        self.assertEqual(deepseek_cost, Decimal("0.001370"))
        self.assertEqual(unknown_cost, Decimal("0.000000"))
        self.assertEqual(LLM_PRICING_VERSION, "llm-pricing-v1-2026-07")

    async def test_success_and_failed_usage_records_are_stored_without_prompt_text(self) -> None:
        _, user_id = await self._auth_headers("18810000001")
        now = datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc)
        async with self.sessionmaker() as db:
            db.add(Session(id=501, user_id=user_id, mode="single", status="ongoing", started_at=now, total_questions=1))
            await db.flush()
            success = await record_llm_usage(
                db,
                user_id=user_id,
                session_id=501,
                request_id="usage-success-1",
                feature="scoring",
                provider="deepseek",
                model="deepseek-chat",
                prompt_tokens=200,
                completion_tokens=80,
                latency_ms=1234,
                status="success",
            )
            failed = await record_llm_usage(
                db,
                user_id=user_id,
                session_id=501,
                request_id="usage-failed-1",
                feature="follow_up",
                provider="deepseek",
                model="deepseek-chat",
                prompt_tokens=120,
                completion_tokens=0,
                latency_ms=650,
                status="failed",
                error_type="LLMResponseError",
            )
            await db.commit()

        self.assertEqual(success.total_tokens, 280)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_type, "LLMResponseError")

        sensitive_columns = {"prompt", "prompt_text", "completion", "completion_text", "answer", "answer_text"}
        self.assertTrue(sensitive_columns.isdisjoint(LLMUsageRecord.__table__.columns.keys()))

        async with self.sessionmaker() as db:
            records = (await db.execute(select(LLMUsageRecord).order_by(LLMUsageRecord.id))).scalars().all()
        self.assertEqual([item.request_id for item in records], ["usage-success-1", "usage-failed-1"])

    async def test_usage_summary_is_current_user_scoped_and_aggregated(self) -> None:
        user_a_headers, user_a_id = await self._auth_headers("18810000002")
        user_b_headers, user_b_id = await self._auth_headers("18810000003")
        now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)

        async with self.sessionmaker() as db:
            db.add_all(
                [
                    Session(id=601, user_id=user_a_id, mode="single", status="finished", started_at=now, total_questions=1),
                    Session(id=602, user_id=user_b_id, mode="single", status="finished", started_at=now, total_questions=1),
                ]
            )
            await db.flush()
            await record_llm_usage(
                db,
                user_id=user_a_id,
                session_id=601,
                request_id="usage-a-1",
                feature="scoring",
                provider="deepseek",
                model="deepseek-chat",
                prompt_tokens=1000,
                completion_tokens=500,
                latency_ms=900,
                status="success",
            )
            await record_llm_usage(
                db,
                user_id=user_a_id,
                session_id=601,
                request_id="usage-a-2",
                feature="follow_up",
                provider="mock",
                model="local-fallback",
                prompt_tokens=50,
                completion_tokens=20,
                latency_ms=10,
                status="failed",
                error_type="RuntimeError",
            )
            await record_llm_usage(
                db,
                user_id=user_b_id,
                session_id=602,
                request_id="usage-b-1",
                feature="scoring",
                provider="deepseek",
                model="deepseek-chat",
                prompt_tokens=9999,
                completion_tokens=9999,
                latency_ms=800,
                status="success",
            )
            await db.commit()

        response = await self.client.get("/api/me/usage/summary", headers=user_a_headers)
        self.assertEqual(response.status_code, 200)
        summary = response.json()

        self.assertEqual(summary["total_tokens"], 1570)
        self.assertEqual(summary["current_month_tokens"], 1570)
        self.assertEqual(summary["pricing_version"], LLM_PRICING_VERSION)
        self.assertEqual({item["key"] for item in summary["by_feature"]}, {"follow_up", "scoring"})
        self.assertEqual({item["key"] for item in summary["by_model"]}, {"deepseek/deepseek-chat", "mock/local-fallback"})
        self.assertEqual([item["request_id"] for item in summary["recent_records"]], ["usage-a-2", "usage-a-1"])
        self.assertNotIn("usage-b-1", [item["request_id"] for item in summary["recent_records"]])

        async with self.sessionmaker() as db:
            service_summary = await get_user_usage_summary(db, user_a_id)
        self.assertEqual(service_summary["total_tokens"], 1570)

        user_b_response = await self.client.get("/api/me/usage/summary", headers=user_b_headers)
        self.assertEqual(user_b_response.status_code, 200)
        self.assertEqual(user_b_response.json()["total_tokens"], 19998)

    async def test_usage_summary_empty_state(self) -> None:
        headers, _ = await self._auth_headers("18810000004")

        response = await self.client.get("/api/me/usage/summary", headers=headers)

        self.assertEqual(response.status_code, 200)
        summary = response.json()
        self.assertEqual(summary["total_tokens"], 0)
        self.assertEqual(summary["total_estimated_cost"], "0.000000")
        self.assertEqual(summary["by_feature"], [])
        self.assertEqual(summary["by_model"], [])
        self.assertEqual(summary["recent_records"], [])


if __name__ == "__main__":
    unittest.main()
