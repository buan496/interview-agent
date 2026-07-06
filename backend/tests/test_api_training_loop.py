from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import sessions as sessions_api
from app.core.interviewer import EvaluationResult as EngineEvaluationResult
from app.core.interviewer import Verdict
from app.db import get_db
from app.main import app
from app.models import Base, Company, Position, Question, QuestionTag, Tag


class FakeInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-loop-model"})()

    async def evaluate_answer(self, *_args, **_kwargs) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            coverage=0.62,
            correct_points=["Mentioned memory access"],
            missing_points=["IO multiplexing"],
            wrong_points=["Answer is too abstract"],
            action="verdict",
            verdict=Verdict(
                score=62,
                mastery="weak",
                feedback="Good opening, but missing IO multiplexing detail.",
                ideal_answer="Cover memory access, event loop, IO multiplexing, and optimized data structures.",
            ),
        )


class ApiTrainingLoopTest(unittest.IsolatedAsyncioTestCase):
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
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

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

    async def _auth_headers(self) -> dict[str, str]:
        response = await self.client.post("/api/auth/login", json={"phone": "18800000000", "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def test_single_question_answer_persists_report_retention_and_next_plan(self) -> None:
        headers = await self._auth_headers()

        create_response = await self.client.post(
            "/api/sessions",
            headers=headers,
            json={"mode": "single", "question_id": 100},
        )
        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        session_id = created["session_id"]
        sq_id = created["first_question"]["sq_id"]

        with patch.object(sessions_api, "InterviewerEngine", FakeInterviewerEngine):
            async with self.client.stream(
                "POST",
                f"/api/sessions/{session_id}/answer",
                headers=headers,
                json={"sq_id": sq_id, "content": "Redis is fast because it uses memory."},
            ) as response:
                self.assertEqual(response.status_code, 200)
                stream_text = await response.aread()

        self.assertIn(b"event: done", stream_text)

        report_response = await self.client.get(f"/api/sessions/{session_id}/report", headers=headers)
        self.assertEqual(report_response.status_code, 200)
        report = report_response.json()
        self.assertEqual(report["overall_score"], 62)
        self.assertEqual(report["questions"][0]["missing_points"], ["IO multiplexing"])
        self.assertEqual(report["questions"][0]["action_items"], ["Review and restate: IO multiplexing"])

        wrong_book_response = await self.client.get("/api/me/wrong-book", headers=headers)
        self.assertEqual(wrong_book_response.status_code, 200)
        wrong_book = wrong_book_response.json()
        self.assertEqual(wrong_book[0]["question_id"], 100)
        self.assertEqual(wrong_book[0]["last_score"], 62)
        self.assertEqual(wrong_book[0]["fail_count"], 1)

        radar_response = await self.client.get("/api/me/radar", headers=headers)
        self.assertEqual(radar_response.status_code, 200)
        radar = radar_response.json()
        self.assertEqual(radar[0]["tag"], "Redis")
        self.assertEqual(Decimal(str(radar[0]["avg_score"])), Decimal("62.00"))
        self.assertEqual(radar[0]["attempts"], 1)

        reports_response = await self.client.get("/api/me/reports", headers=headers)
        self.assertEqual(reports_response.status_code, 200)
        self.assertEqual(reports_response.json()[0]["session_id"], session_id)

        plan_response = await self.client.get("/api/me/practice-plan/today", headers=headers)
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        self.assertIn("Latest report action items", plan["generated_reason"])
        first_task = plan["recommended_tasks"][0]
        self.assertEqual(first_task["id"], "wrong-book-review")
        self.assertEqual(first_task["payload"], {"mode": "single", "question_id": 100})


if __name__ == "__main__":
    unittest.main()
