from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
import unittest
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
from app.models import AuditEvent, Base, Company, Position, Question, QuestionTag, Tag


class WeakInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-memory-model"})()

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


class AgentMemoryTest(unittest.IsolatedAsyncioTestCase):
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

    async def _auth_headers(self, phone: str = "18800000000") -> dict[str, str]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def _finish_weak_session(self, headers: dict[str, str], answer: str = "Redis is fast because it uses memory.") -> int:
        create_response = await self.client.post("/api/sessions", headers=headers, json={"mode": "single", "question_id": 100})
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        with patch.object(sessions_api, "InterviewerEngine", WeakInterviewerEngine):
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

    async def test_report_completion_generates_user_memory_without_raw_answer(self) -> None:
        headers = await self._auth_headers()
        raw_answer = "my private raw redis answer"

        await self._finish_weak_session(headers, raw_answer)

        response = await self.client.get("/api/me/memories", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 1)
        weakness = next(item for item in payload["items"] if item["memory_type"] == "weakness")
        self.assertEqual(weakness["tags_json"][0]["tag"], "Redis")
        memory_text = str(weakness)
        self.assertNotIn(raw_answer, memory_text)
        self.assertNotIn("prompt", memory_text.lower())
        self.assertNotIn("completion", memory_text.lower())

        async with self.sessionmaker() as db:
            audit_count = await db.scalar(select(AuditEvent).where(AuditEvent.action == "memory_created"))
            self.assertIsNotNone(audit_count)

        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_memories_created_total{memory_type="weakness"}', metrics)
        self.assertIn('interview_agent_memory_refresh_total{status="success",trigger="report"}', metrics)

    async def test_repeated_weakness_updates_existing_memory(self) -> None:
        headers = await self._auth_headers()

        await self._finish_weak_session(headers)
        await self._finish_weak_session(headers, "Redis answer repeated.")

        response = await self.client.get("/api/me/memories?memory_type=weakness", headers=headers)
        self.assertEqual(response.status_code, 200)
        memories = response.json()["items"]
        redis_memories = [item for item in memories if item["tags_json"][0]["tag"] == "Redis"]
        self.assertEqual(len(redis_memories), 1)
        self.assertGreater(Decimal(str(redis_memories[0]["confidence"])), Decimal("0.50"))
        self.assertGreaterEqual(len(redis_memories[0]["evidence_json"]), 2)

    async def test_user_memory_list_and_archive_are_current_user_scoped(self) -> None:
        user_a = await self._auth_headers("18800000001")
        user_b = await self._auth_headers("18800000002")
        await self._finish_weak_session(user_b)

        user_a_response = await self.client.get("/api/me/memories", headers=user_a)
        self.assertEqual(user_a_response.status_code, 200)
        self.assertEqual(user_a_response.json()["items"], [])

        user_b_response = await self.client.get("/api/me/memories?memory_type=weakness", headers=user_b)
        self.assertEqual(user_b_response.status_code, 200)
        memory_id = user_b_response.json()["items"][0]["id"]

        denied = await self.client.post(f"/api/me/memories/{memory_id}/archive", headers=user_a)
        self.assertEqual(denied.status_code, 404)

        archived = await self.client.post(f"/api/me/memories/{memory_id}/archive", headers=user_b)
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["status"], "archived")

        active_after_archive = await self.client.get("/api/me/memories?memory_type=weakness", headers=user_b)
        self.assertEqual(active_after_archive.status_code, 200)
        self.assertEqual(active_after_archive.json()["items"], [])

    async def test_archived_memory_does_not_participate_in_practice_plan(self) -> None:
        headers = await self._auth_headers()
        await self._finish_weak_session(headers)
        response = await self.client.get("/api/me/memories?memory_type=weakness", headers=headers)
        memory_id = response.json()["items"][0]["id"]
        await self.client.post(f"/api/me/memories/{memory_id}/archive", headers=headers)

        plan_response = await self.client.get("/api/me/practice-plan/today", headers=headers)
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        self.assertTrue(all(item.get("memory_id") != memory_id for item in plan["weak_tags"]))

    async def test_memory_refresh_failure_does_not_break_answer_flow(self) -> None:
        headers = await self._auth_headers()

        with patch("app.api.sessions.refresh_memories_from_session_report", side_effect=RuntimeError("memory failed")):
            session_id = await self._finish_weak_session(headers)

        report_response = await self.client.get(f"/api/sessions/{session_id}/report", headers=headers)
        self.assertEqual(report_response.status_code, 200)
        metrics = metrics_content().decode("utf-8")
        self.assertIn('interview_agent_memory_refresh_total{status="failed",trigger="report"}', metrics)


if __name__ == "__main__":
    unittest.main()
