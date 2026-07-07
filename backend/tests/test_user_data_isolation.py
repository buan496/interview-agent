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


class FakeWeakInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-isolation-model"})()

    async def evaluate_answer(self, *_args, **_kwargs) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            coverage=0.58,
            correct_points=["Mentioned memory access"],
            missing_points=["IO multiplexing"],
            wrong_points=["Answer is too high level"],
            action="verdict",
            verdict=Verdict(
                score=58,
                mastery="weak",
                feedback="The answer needs more detail on IO multiplexing.",
                ideal_answer="Cover memory access, event loop, IO multiplexing, and optimized data structures.",
            ),
        )


class UserDataIsolationTest(unittest.IsolatedAsyncioTestCase):
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

    async def _auth_headers(self, phone: str) -> dict[str, str]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def _create_single_session(self, headers: dict[str, str]) -> tuple[int, int]:
        response = await self.client.post(
            "/api/sessions",
            headers=headers,
            json={"mode": "single", "question_id": 100},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["session_id"], payload["first_question"]["sq_id"]

    async def _finish_session_with_weak_score(self, headers: dict[str, str], session_id: int, sq_id: int) -> None:
        with patch.object(sessions_api, "InterviewerEngine", FakeWeakInterviewerEngine):
            async with self.client.stream(
                "POST",
                f"/api/sessions/{session_id}/answer",
                headers=headers,
                json={"sq_id": sq_id, "content": "Redis is fast because it stores data in memory."},
            ) as response:
                self.assertEqual(response.status_code, 200)
                stream_text = await response.aread()
        self.assertIn(b"event: done", stream_text)

    async def test_training_resources_are_isolated_by_current_user(self) -> None:
        user_a_headers = await self._auth_headers("18800000001")
        user_b_headers = await self._auth_headers("18800000002")

        session_id, sq_id = await self._create_single_session(user_a_headers)

        own_session_response = await self.client.get(f"/api/sessions/{session_id}", headers=user_a_headers)
        self.assertEqual(own_session_response.status_code, 200)

        cross_session_response = await self.client.get(f"/api/sessions/{session_id}", headers=user_b_headers)
        self.assertEqual(cross_session_response.status_code, 404)

        async with self.client.stream(
            "POST",
            f"/api/sessions/{session_id}/answer",
            headers=user_b_headers,
            json={"sq_id": sq_id, "content": "Trying to write into another user's session."},
        ) as response:
            self.assertEqual(response.status_code, 404)

        await self._finish_session_with_weak_score(user_a_headers, session_id, sq_id)

        own_report_response = await self.client.get(f"/api/sessions/{session_id}/report", headers=user_a_headers)
        self.assertEqual(own_report_response.status_code, 200)
        self.assertEqual(own_report_response.json()["overall_score"], 58)

        cross_report_response = await self.client.get(f"/api/sessions/{session_id}/report", headers=user_b_headers)
        self.assertEqual(cross_report_response.status_code, 404)

        user_a_reports_response = await self.client.get("/api/me/reports", headers=user_a_headers)
        self.assertEqual(user_a_reports_response.status_code, 200)
        self.assertEqual([item["session_id"] for item in user_a_reports_response.json()], [session_id])

        user_b_reports_response = await self.client.get("/api/me/reports", headers=user_b_headers)
        self.assertEqual(user_b_reports_response.status_code, 200)
        self.assertEqual(user_b_reports_response.json(), [])

        user_a_wrong_book_response = await self.client.get("/api/me/wrong-book", headers=user_a_headers)
        self.assertEqual(user_a_wrong_book_response.status_code, 200)
        self.assertEqual([item["question_id"] for item in user_a_wrong_book_response.json()], [100])

        user_b_wrong_book_response = await self.client.get("/api/me/wrong-book", headers=user_b_headers)
        self.assertEqual(user_b_wrong_book_response.status_code, 200)
        self.assertEqual(user_b_wrong_book_response.json(), [])

        user_a_radar_response = await self.client.get("/api/me/radar", headers=user_a_headers)
        self.assertEqual(user_a_radar_response.status_code, 200)
        user_a_radar = user_a_radar_response.json()
        self.assertEqual(user_a_radar[0]["tag"], "Redis")
        self.assertEqual(Decimal(str(user_a_radar[0]["avg_score"])), Decimal("58.00"))

        user_b_radar_response = await self.client.get("/api/me/radar", headers=user_b_headers)
        self.assertEqual(user_b_radar_response.status_code, 200)
        self.assertEqual(user_b_radar_response.json(), [])

        active_session_id, _ = await self._create_single_session(user_a_headers)

        user_a_plan_response = await self.client.get("/api/me/practice-plan/today", headers=user_a_headers)
        self.assertEqual(user_a_plan_response.status_code, 200)
        user_a_plan = user_a_plan_response.json()
        self.assertEqual(user_a_plan["recommended_tasks"][0]["type"], "resume_session")
        self.assertEqual(user_a_plan["recommended_tasks"][0]["payload"]["session_id"], active_session_id)
        self.assertIn("Redis", [item["tag"] for item in user_a_plan["weak_tags"]])

        user_b_plan_response = await self.client.get("/api/me/practice-plan/today", headers=user_b_headers)
        self.assertEqual(user_b_plan_response.status_code, 200)
        user_b_plan = user_b_plan_response.json()
        self.assertEqual(user_b_plan["weak_tags"], [])
        self.assertNotIn("resume_session", [item["type"] for item in user_b_plan["recommended_tasks"]])
        self.assertNotIn("wrong_book_review", [item["type"] for item in user_b_plan["recommended_tasks"]])

        cross_complete_response = await self.client.post(
            f"/api/me/practice-plan/{user_a_plan['id']}/complete",
            headers=user_b_headers,
        )
        self.assertEqual(cross_complete_response.status_code, 404)

        own_complete_response = await self.client.post(
            f"/api/me/practice-plan/{user_a_plan['id']}/complete",
            headers=user_a_headers,
        )
        self.assertEqual(own_complete_response.status_code, 200)
        self.assertTrue(own_complete_response.json()["completed"])


if __name__ == "__main__":
    unittest.main()
