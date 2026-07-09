from __future__ import annotations

import asyncio
import json
import unittest
from decimal import Decimal
from collections.abc import AsyncIterator
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import sessions as sessions_api
from app.core.interviewer import EvaluationResult as EngineEvaluationResult
from app.core.interviewer import Verdict
from app.db import get_db
from app.main import app
from app.metrics import metrics_content
from app.models import AsyncJob, AuditEvent, Base, Company, LLMUsageRecord, Position, Question, QuestionTag, Tag, User


class PrivacyInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-privacy-model"})()

    async def evaluate_answer(self, *_args, **_kwargs) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            coverage=0.58,
            correct_points=["Mentioned memory"],
            missing_points=["IO multiplexing"],
            wrong_points=["Too generic"],
            action="verdict",
            verdict=Verdict(
                score=58,
                mastery="weak",
                feedback="Needs stronger Redis fundamentals.",
                ideal_answer="Cover memory access, event loop, IO multiplexing, and data structures.",
            ),
        )


class PrivacyDataLifecycleTest(unittest.IsolatedAsyncioTestCase):
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
        await self._seed_question()

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            async with self.sessionmaker() as session:
                yield session

        self.original_session_local = sessions_api.SessionLocal
        sessions_api.SessionLocal = self.sessionmaker
        app.dependency_overrides[get_db] = override_get_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        sessions_api.SessionLocal = self.original_session_local
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

    async def _auth_headers(self, phone: str) -> dict[str, str]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def _user_id_by_phone(self, phone: str) -> int:
        async with self.sessionmaker() as db:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
            return int(user.id)

    async def _finish_session(self, headers: dict[str, str], answer: str) -> int:
        create_response = await self.client.post("/api/sessions", headers=headers, json={"mode": "single", "question_id": 100})
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        with patch.object(sessions_api, "InterviewerEngine", PrivacyInterviewerEngine):
            async with self.client.stream(
                "POST",
                f"/api/sessions/{created['session_id']}/answer",
                headers=headers,
                json={"sq_id": created["first_question"]["sq_id"], "content": answer},
            ) as response:
                self.assertEqual(response.status_code, 200)
                stream_text = await response.aread()
        self.assertIn(b"event: done", stream_text)
        return int(created["session_id"])

    async def _seed_sensitive_summaries(self, user_id: int, session_id: int) -> None:
        async with self.sessionmaker() as db:
            db.add(
                AsyncJob(
                    user_id=user_id,
                    job_type="memory_refresh",
                    status="queued",
                    payload_json={"user_id": user_id, "answer_text": "raw async private answer", "token": "secret-token"},
                    attempts=0,
                    max_attempts=3,
                )
            )
            db.add(
                LLMUsageRecord(
                    user_id=user_id,
                    session_id=session_id,
                    request_id="privacy-test-request",
                    feature="interview_scoring",
                    provider="mock",
                    model="mock-model",
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    estimated_cost=Decimal("0.001000"),
                    currency="USD",
                    pricing_version="test-pricing",
                    latency_ms=12,
                    status="success",
                )
            )
            await db.commit()

    async def test_data_summary_and_export_are_current_user_scoped_and_redacted(self) -> None:
        phone = "18800009991"
        raw_answer = "my private raw redis answer for export"
        headers = await self._auth_headers(phone)
        session_id = await self._finish_session(headers, raw_answer)
        user_id = await self._user_id_by_phone(phone)
        await self._seed_sensitive_summaries(user_id, session_id)
        await self.client.get("/api/me/practice-plan/today", headers=headers)

        summary_response = await self.client.get("/api/me/data-summary", headers=headers)
        self.assertEqual(summary_response.status_code, 200)
        counts = summary_response.json()["counts"]
        self.assertEqual(counts["sessions"], 1)
        self.assertGreaterEqual(counts["agent_memories"], 1)
        self.assertEqual(counts["async_jobs"], 1)
        self.assertEqual(counts["llm_usage_records"], 1)

        export_response = await self.client.get("/api/me/data-export", headers=headers)
        self.assertEqual(export_response.status_code, 200)
        payload = export_response.json()
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["user"]["phone_masked"], "188****9991")
        self.assertNotIn(phone, serialized)
        self.assertNotIn(raw_answer, serialized)
        self.assertNotIn("raw async private answer", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("000000", serialized)
        self.assertNotIn("raw_model_output", serialized)
        self.assertIn("<redacted>", serialized)

        async with self.sessionmaker() as db:
            audit = (await db.execute(select(AuditEvent).where(AuditEvent.action == "user_data_exported"))).scalar_one_or_none()
            self.assertIsNotNone(audit)
            self.assertNotIn(raw_answer, json.dumps(audit.metadata_json, ensure_ascii=False))

        self.assertIn('interview_agent_data_exports_total{status="success"}', metrics_content().decode("utf-8"))

    async def test_data_delete_requires_confirmation_and_writes_audit(self) -> None:
        headers = await self._auth_headers("18800009992")

        denied = await self.client.post("/api/me/data-delete-confirm", headers=headers, json={"confirmation_phrase": "WRONG"})
        self.assertEqual(denied.status_code, 400)

        async with self.sessionmaker() as db:
            audit = (await db.execute(select(AuditEvent).where(AuditEvent.action == "user_data_delete_denied"))).scalar_one_or_none()
            self.assertIsNotNone(audit)

        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_data_deletions_total{scope="training_data",status="denied"}', metrics)

    async def test_data_delete_removes_only_current_user_training_data(self) -> None:
        user_a_phone = "18800009993"
        user_b_phone = "18800009994"
        user_a = await self._auth_headers(user_a_phone)
        user_b = await self._auth_headers(user_b_phone)
        session_a = await self._finish_session(user_a, "private answer user A")
        session_b = await self._finish_session(user_b, "private answer user B")
        await self.client.get("/api/me/practice-plan/today", headers=user_a)
        await self.client.get("/api/me/practice-plan/today", headers=user_b)
        await self._seed_sensitive_summaries(await self._user_id_by_phone(user_a_phone), session_a)
        await self._seed_sensitive_summaries(await self._user_id_by_phone(user_b_phone), session_b)

        request_response = await self.client.post("/api/me/data-deletion-request", headers=user_a)
        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(request_response.json()["confirmation_phrase"], "DELETE_MY_DATA")

        delete_response = await self.client.post(
            "/api/me/data-delete-confirm",
            headers=user_a,
            json={"confirmation_phrase": "DELETE_MY_DATA"},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["scope"], "training_data")

        summary_after = await self.client.get("/api/me/data-summary", headers=user_a)
        self.assertEqual(summary_after.status_code, 200)
        for count in summary_after.json()["counts"].values():
            self.assertEqual(count, 0)

        self.assertEqual((await self.client.get("/api/me/reports", headers=user_a)).json(), [])
        self.assertEqual((await self.client.get("/api/me/wrong-book", headers=user_a)).json(), [])
        self.assertEqual((await self.client.get("/api/me/memories", headers=user_a)).json()["items"], [])

        user_b_reports = await self.client.get("/api/me/reports", headers=user_b)
        self.assertEqual(user_b_reports.status_code, 200)
        self.assertEqual(len(user_b_reports.json()), 1)
        user_b_summary = await self.client.get("/api/me/data-summary", headers=user_b)
        self.assertGreater(user_b_summary.json()["counts"]["sessions"], 0)

        async with self.sessionmaker() as db:
            audit = (await db.execute(select(AuditEvent).where(AuditEvent.action == "user_data_deleted"))).scalar_one_or_none()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.target_user_id, await self._user_id_by_phone(user_a_phone))

        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_data_deletions_total{scope="training_data",status="success"}', metrics)


if __name__ == "__main__":
    unittest.main()
