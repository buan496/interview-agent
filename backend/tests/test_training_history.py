from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
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


class FakeHistoryInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-history-model"})()

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


class TrainingHistoryTest(unittest.IsolatedAsyncioTestCase):
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

    async def _finish_session(self, headers: dict[str, str], session_id: int, sq_id: int) -> None:
        with patch.object(sessions_api, "InterviewerEngine", FakeHistoryInterviewerEngine):
            async with self.client.stream(
                "POST",
                f"/api/sessions/{session_id}/answer",
                headers=headers,
                json={"sq_id": sq_id, "content": "Redis is fast because it stores data in memory."},
            ) as response:
                self.assertEqual(response.status_code, 200)
                stream_text = await response.aread()
        self.assertIn(b"event: done", stream_text)

    async def test_history_is_current_user_scoped_and_time_ordered(self) -> None:
        user_a_headers = await self._auth_headers("18800000001")
        user_b_headers = await self._auth_headers("18800000002")
        user_c_headers = await self._auth_headers("18800000003")

        empty_response = await self.client.get("/api/sessions/history", headers=user_c_headers)
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json(), [])

        finished_session_id, finished_sq_id = await self._create_single_session(user_a_headers)
        await self._finish_session(user_a_headers, finished_session_id, finished_sq_id)
        active_session_id, _ = await self._create_single_session(user_a_headers)
        user_b_session_id, _ = await self._create_single_session(user_b_headers)

        user_a_history_response = await self.client.get("/api/sessions/history", headers=user_a_headers)
        self.assertEqual(user_a_history_response.status_code, 200)
        user_a_history = user_a_history_response.json()
        self.assertEqual([item["session_id"] for item in user_a_history], [active_session_id, finished_session_id])
        self.assertNotIn(user_b_session_id, [item["session_id"] for item in user_a_history])

        active_item = user_a_history[0]
        self.assertEqual(active_item["status"], "ongoing")
        self.assertEqual(active_item["next_action"], "continue")
        self.assertIsNone(active_item["report_id"])
        self.assertIsNone(active_item["overall_score"])
        self.assertEqual(active_item["question_count"], 1)
        self.assertEqual(active_item["title"], "Why is Redis fast?")

        finished_item = user_a_history[1]
        self.assertEqual(finished_item["status"], "finished")
        self.assertEqual(finished_item["next_action"], "view_report")
        self.assertEqual(finished_item["report_id"], finished_session_id)
        self.assertEqual(finished_item["overall_score"], 58)
        self.assertEqual(finished_item["weak_tags"], ["Redis"])
        self.assertIsNotNone(finished_item["completed_at"])

        user_b_history_response = await self.client.get("/api/sessions/history", headers=user_b_headers)
        self.assertEqual(user_b_history_response.status_code, 200)
        user_b_history = user_b_history_response.json()
        self.assertEqual([item["session_id"] for item in user_b_history], [user_b_session_id])
        self.assertNotIn(finished_session_id, [item["session_id"] for item in user_b_history])

    async def test_history_supports_limit_and_offset(self) -> None:
        headers = await self._auth_headers("18800000004")
        first_session_id, _ = await self._create_single_session(headers)
        second_session_id, _ = await self._create_single_session(headers)

        first_page_response = await self.client.get("/api/sessions/history?limit=1", headers=headers)
        self.assertEqual(first_page_response.status_code, 200)
        self.assertEqual([item["session_id"] for item in first_page_response.json()], [second_session_id])

        second_page_response = await self.client.get("/api/sessions/history?limit=1&offset=1", headers=headers)
        self.assertEqual(second_page_response.status_code, 200)
        self.assertEqual([item["session_id"] for item in second_page_response.json()], [first_session_id])


if __name__ == "__main__":
    unittest.main()
