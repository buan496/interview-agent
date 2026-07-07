from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import (
    Base,
    Company,
    EvaluationResult,
    Position,
    Question,
    QuestionTag,
    Session,
    SessionQuestion,
    Tag,
    User,
    UserTagStat,
    WrongBook,
)


class AbilityProfileTest(unittest.IsolatedAsyncioTestCase):
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

        await self._seed_questions()

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

    async def _seed_questions(self) -> None:
        async with self.sessionmaker() as db:
            company = Company(id=1, name="General Co", region="CN", tier=1)
            position = Position(id=1, name="Agent Engineer")
            redis_tag = Tag(id=7, name="Redis", category="knowledge")
            system_design_tag = Tag(id=8, name="System Design", category="ability")
            redis_question = Question(
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
            system_design_question = Question(
                id=101,
                title="Design an Agent tool execution pipeline.",
                answer_key="Cover planning, tool contracts, retries, observability, and safety boundaries.",
                difficulty=4,
                qtype="system_design",
                source_type="seed",
                company_id=company.id,
                position_id=position.id,
                status="active",
            )
            db.add_all([company, position, redis_tag, system_design_tag, redis_question, system_design_question])
            await db.flush()
            db.add_all(
                [
                    QuestionTag(question_id=redis_question.id, tag_id=redis_tag.id),
                    QuestionTag(question_id=system_design_question.id, tag_id=system_design_tag.id),
                ]
            )
            await db.commit()

    async def _auth_headers(self, phone: str) -> tuple[dict[str, str], int]:
        response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        async with self.sessionmaker() as db:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}, user.id

    async def _seed_user_profile(self, user_id: int, *, session_id: int, score: int) -> None:
        now = datetime(2026, 7, 7, 8, 0, tzinfo=timezone.utc)
        async with self.sessionmaker() as db:
            session = Session(
                id=session_id,
                user_id=user_id,
                mode="mock",
                status="finished",
                report={"overall_score": score},
                started_at=now - timedelta(days=1),
                finished_at=now,
                ended_at=now,
                total_questions=2,
                updated_at=now,
            )
            redis_sq = SessionQuestion(
                id=session_id * 10 + 1,
                session_id=session.id,
                question_id=100,
                order_no=1,
                status="scored",
                final_score=92,
                mastery="pass",
                started_at=now - timedelta(days=1),
                submitted_at=now - timedelta(days=1, minutes=-10),
                scored_at=now - timedelta(days=1, minutes=-9),
                finished_at=now - timedelta(days=1, minutes=-9),
            )
            system_design_sq = SessionQuestion(
                id=session_id * 10 + 2,
                session_id=session.id,
                question_id=101,
                order_no=2,
                status="scored",
                final_score=58,
                mastery="weak",
                started_at=now - timedelta(hours=2),
                submitted_at=now - timedelta(hours=1, minutes=50),
                scored_at=now - timedelta(hours=1, minutes=49),
                finished_at=now - timedelta(hours=1, minutes=49),
            )
            db.add_all(
                [
                    session,
                    redis_sq,
                    system_design_sq,
                    UserTagStat(user_id=user_id, tag_id=7, attempts=3, avg_score=Decimal("92.00")),
                    UserTagStat(user_id=user_id, tag_id=8, attempts=2, avg_score=Decimal("58.00")),
                    WrongBook(user_id=user_id, question_id=101, last_score=42, fail_count=3),
                    EvaluationResult(
                        id=session_id * 100 + 1,
                        user_id=user_id,
                        session_id=session.id,
                        sq_id=redis_sq.id,
                        question_id=100,
                        score=92,
                        mastery="pass",
                        verdict="Strong answer.",
                        created_at=now - timedelta(days=1),
                    ),
                    EvaluationResult(
                        id=session_id * 100 + 2,
                        user_id=user_id,
                        session_id=session.id,
                        sq_id=system_design_sq.id,
                        question_id=101,
                        score=58,
                        mastery="weak",
                        verdict="Needs better system boundaries.",
                        created_at=now,
                    ),
                ]
            )
            await db.commit()

    async def test_ability_profile_is_current_user_scoped_and_aggregated(self) -> None:
        user_a_headers, user_a_id = await self._auth_headers("18800000101")
        user_b_headers, user_b_id = await self._auth_headers("18800000102")
        await self._seed_user_profile(user_a_id, session_id=301, score=76)

        async with self.sessionmaker() as db:
            db.add(UserTagStat(user_id=user_b_id, tag_id=7, attempts=1, avg_score=Decimal("20.00")))
            await db.commit()

        user_a_response = await self.client.get("/api/me/ability-profile", headers=user_a_headers)
        self.assertEqual(user_a_response.status_code, 200)
        profile = user_a_response.json()

        self.assertEqual(profile["overall_score"], 76)
        self.assertEqual(profile["total_sessions"], 1)
        self.assertEqual(profile["completed_sessions"], 1)
        self.assertEqual(profile["total_questions"], 2)
        self.assertEqual([item["tag"] for item in profile["strengths"]], ["Redis"])
        self.assertEqual(profile["strengths"][0]["mastery_level"], "strong")
        self.assertEqual([item["tag"] for item in profile["weaknesses"]], ["System Design"])
        self.assertEqual(profile["weaknesses"][0]["wrong_count"], 3)
        self.assertEqual(profile["weaknesses"][0]["mastery_level"], "weak")
        self.assertEqual({item["tag"] for item in profile["tag_profiles"]}, {"Redis", "System Design"})
        self.assertIsNotNone(profile["updated_at"])

        user_b_response = await self.client.get("/api/me/ability-profile", headers=user_b_headers)
        self.assertEqual(user_b_response.status_code, 200)
        user_b_profile = user_b_response.json()
        self.assertEqual(user_b_profile["overall_score"], None)
        self.assertEqual(user_b_profile["total_sessions"], 0)
        self.assertEqual([item["tag"] for item in user_b_profile["tag_profiles"]], ["Redis"])
        self.assertEqual(Decimal(str(user_b_profile["tag_profiles"][0]["average_score"])), Decimal("20.00"))
        self.assertNotIn("System Design", [item["tag"] for item in user_b_profile["tag_profiles"]])

    async def test_ability_profile_empty_state(self) -> None:
        headers, _ = await self._auth_headers("18800000103")

        response = await self.client.get("/api/me/ability-profile", headers=headers)
        self.assertEqual(response.status_code, 200)
        profile = response.json()

        self.assertIsNone(profile["overall_score"])
        self.assertEqual(profile["total_sessions"], 0)
        self.assertEqual(profile["completed_sessions"], 0)
        self.assertEqual(profile["total_questions"], 0)
        self.assertIsNone(profile["updated_at"])
        self.assertEqual(profile["strengths"], [])
        self.assertEqual(profile["weaknesses"], [])
        self.assertEqual(profile["tag_profiles"], [])


if __name__ == "__main__":
    unittest.main()
