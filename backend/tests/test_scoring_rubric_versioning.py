from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

from app.api import sessions as sessions_api
from app.core.interviewer import EvaluationResult as EngineEvaluationResult
from app.core.interviewer import Verdict
from app.db import get_db
from app.main import app
from app.models import AuditEvent, Base, EvaluationResult, Question, ScoringRubricVersion, User
from app.rbac import ROLE_ADMIN, ROLE_CONTENT_OPERATOR
from app.rubrics import SYSTEM_DEFAULT_RUBRIC_NAME


def _auth_settings(admin_phone_set: set[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        is_production=False,
        auth_dev_code_enabled=True,
        auth_dev_code="000000",
        sms_provider_key="",
        jwt_secret="rubric-test-secret",
        access_token_expire_minutes=60,
        admin_phone_set=admin_phone_set or set(),
    )


class FakeInterviewerEngine:
    def __init__(self) -> None:
        self.llm = type("FakeLlm", (), {"model": "fake-rubric-model"})()
        self.last_llm_call_attempted = False
        self.last_llm_call_failed = False
        self.last_llm_error_type = None

    async def evaluate_answer(self, *_args, **_kwargs) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            coverage=0.88,
            correct_points=["Explained core tradeoffs"],
            missing_points=["Add failure-mode examples"],
            wrong_points=[],
            action="verdict",
            verdict=Verdict(
                score=88,
                mastery="pass",
                feedback="Structured answer with clear tradeoffs.",
                ideal_answer="Cover correctness, completeness, expression, and engineering depth.",
            ),
        )


class ScoringRubricVersioningTest(unittest.IsolatedAsyncioTestCase):
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

    async def _login(self, phone: str) -> str:
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            response = await self.client.post("/api/auth/login", json={"phone": phone, "code": "000000"})
        self.assertEqual(response.status_code, 200)
        return str(response.json()["access_token"])

    async def _set_user_role(self, phone: str, role: str) -> None:
        async with self.sessionmaker() as db:
            user = (await db.execute(select(User).where(User.phone == phone))).scalar_one()
            user.role = role
            await db.commit()

    async def _audit_events(self) -> list[AuditEvent]:
        async with self.sessionmaker() as db:
            return (await db.execute(select(AuditEvent).order_by(AuditEvent.id))).scalars().all()

    async def _create_published_rubric_version(self, token: str, name: str, version: str = "v1") -> int:
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            rubric = await self.client.post(
                "/api/admin/rubrics",
                json={"name": name, "description": "Rubric for tests.", "status": "draft"},
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"{name}-create"},
            )
            self.assertEqual(rubric.status_code, 200)
            version_response = await self.client.post(
                f"/api/admin/rubrics/{rubric.json()['id']}/versions",
                json={
                    "version": version,
                    "dimensions_json": [{"key": "correctness", "weight": 100}],
                    "prompt_template": "Score the answer using correctness, completeness, expression, and depth.",
                    "scoring_scale": "0-100",
                },
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"{name}-{version}-create"},
            )
            self.assertEqual(version_response.status_code, 200)
            published = await self.client.post(
                f"/api/admin/rubric-versions/{version_response.json()['id']}/publish",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"{name}-{version}-publish"},
            )
            self.assertEqual(published.status_code, 200)
        return int(published.json()["id"])

    async def _seed_question(self, question_id: int, rubric_version_id: int | None = None) -> None:
        async with self.sessionmaker() as db:
            db.add(
                Question(
                    id=question_id,
                    title=f"Question {question_id}: design an Agent scoring workflow?",
                    body="Cover scoring workflow and version traceability.",
                    answer_key="Answer should cover versioned rubric, audit, reports, and historical traceability.",
                    difficulty=3,
                    qtype="system_design",
                    source_type="managed",
                    status="published",
                    default_rubric_version_id=rubric_version_id,
                )
            )
            await db.commit()

    async def _complete_single_question_session(self, token: str, question_id: int) -> tuple[int, dict]:
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            created = await self.client.post(
                "/api/sessions",
                json={"mode": "single", "question_id": question_id},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(created.status_code, 200)
            session_id = created.json()["session_id"]
            sq_id = created.json()["first_question"]["sq_id"]
            with patch.object(sessions_api, "InterviewerEngine", FakeInterviewerEngine):
                async with self.client.stream(
                    "POST",
                    f"/api/sessions/{session_id}/answer",
                    json={"sq_id": sq_id, "content": "Use a versioned rubric and persist the selected rubric version."},
                    headers={"Authorization": f"Bearer {token}"},
                ) as answer_response:
                    self.assertEqual(answer_response.status_code, 200)
                    await answer_response.aread()
            report = await self.client.get(f"/api/sessions/{session_id}/report", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(report.status_code, 200)
        return session_id, report.json()

    async def test_admin_and_content_operator_can_manage_rubrics_and_audit_events(self) -> None:
        admin_token = await self._login("18800004001")
        operator_token = await self._login("18800004002")
        await self._set_user_role("18800004001", ROLE_ADMIN)
        await self._set_user_role("18800004002", ROLE_CONTENT_OPERATOR)

        admin_version_id = await self._create_published_rubric_version(admin_token, "admin-rubric", "v1")
        operator_version_id = await self._create_published_rubric_version(operator_token, "operator-rubric", "v1")

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            archived = await self.client.post(
                f"/api/admin/rubric-versions/{operator_version_id}/archive",
                headers={"Authorization": f"Bearer {operator_token}", "X-Request-ID": "operator-rubric-archive"},
            )
            listed = await self.client.get("/api/admin/rubrics", headers={"Authorization": f"Bearer {admin_token}"})

        self.assertEqual(archived.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(listed.json()["total"], 2)
        self.assertGreater(admin_version_id, 0)

        actions = [event.action for event in await self._audit_events()]
        self.assertIn("rubric_created", actions)
        self.assertIn("rubric_version_created", actions)
        self.assertIn("rubric_version_published", actions)
        self.assertIn("rubric_version_archived", actions)

    async def test_regular_user_cannot_create_rubric_and_denial_is_audited(self) -> None:
        user_token = await self._login("18800004003")

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            denied = await self.client.post(
                "/api/admin/rubrics",
                json={"name": "denied-rubric"},
                headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "rubric-user-denied"},
            )

        self.assertEqual(denied.status_code, 403)
        events = await self._audit_events()
        denied_event = next(event for event in events if event.action == "rubric_denied")
        self.assertEqual(denied_event.request_id, "rubric-user-denied")
        self.assertEqual(denied_event.reason, "rubric_rbac_denied")

    async def test_scoring_records_rubric_version_and_historical_report_is_stable(self) -> None:
        admin_token = await self._login("18800004004")
        user_token = await self._login("18800004005")
        await self._set_user_role("18800004004", ROLE_ADMIN)
        rubric_v1_id = await self._create_published_rubric_version(admin_token, "traceable-rubric", "v1")
        await self._seed_question(4201, rubric_v1_id)

        session_id, report = await self._complete_single_question_session(user_token, 4201)
        self.assertEqual(report["questions"][0]["rubric_version_id"], rubric_v1_id)

        async with self.sessionmaker() as db:
            evaluation = (await db.execute(select(EvaluationResult).where(EvaluationResult.session_id == session_id))).scalar_one()
            self.assertEqual(evaluation.rubric_version_id, rubric_v1_id)
            self.assertEqual(evaluation.raw_model_output["rubric"]["rubric_version_id"], rubric_v1_id)
            rubric_v1 = await db.get(ScoringRubricVersion, rubric_v1_id)
            assert rubric_v1 is not None
            rubric_id = rubric_v1.rubric_id

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            rubric_v2 = await self.client.post(
                f"/api/admin/rubrics/{rubric_id}/versions",
                json={
                    "version": "v2",
                    "dimensions_json": [{"key": "depth", "weight": 100}],
                    "prompt_template": "Score the answer with a stricter engineering-depth rubric.",
                    "scoring_scale": "0-100",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(rubric_v2.status_code, 200)
            published_v2 = await self.client.post(
                f"/api/admin/rubric-versions/{rubric_v2.json()['id']}/publish",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            self.assertEqual(published_v2.status_code, 200)
        rubric_v2_id = int(published_v2.json()["id"])
        self.assertNotEqual(rubric_v1_id, rubric_v2_id)
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            report_after_new_version = await self.client.get(f"/api/sessions/{session_id}/report", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(report_after_new_version.status_code, 200)
        self.assertEqual(report_after_new_version.json()["questions"][0]["rubric_version_id"], rubric_v1_id)

    async def test_archived_question_default_rubric_version_is_not_used_for_new_scoring(self) -> None:
        admin_token = await self._login("18800004006")
        user_token = await self._login("18800004007")
        await self._set_user_role("18800004006", ROLE_ADMIN)
        archived_version_id = await self._create_published_rubric_version(admin_token, "archive-before-scoring", "v1")

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            archived = await self.client.post(
                f"/api/admin/rubric-versions/{archived_version_id}/archive",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        self.assertEqual(archived.status_code, 200)
        await self._seed_question(4202, archived_version_id)

        session_id, report = await self._complete_single_question_session(user_token, 4202)
        used_rubric_version_id = report["questions"][0]["rubric_version_id"]
        self.assertNotEqual(used_rubric_version_id, archived_version_id)

        async with self.sessionmaker() as db:
            used_version = (
                await db.execute(
                    select(ScoringRubricVersion)
                    .where(ScoringRubricVersion.id == used_rubric_version_id)
                    .options(selectinload(ScoringRubricVersion.rubric))
                )
            ).scalar_one_or_none()
            self.assertIsNotNone(used_version)
            assert used_version is not None
            self.assertEqual(used_version.rubric.name, SYSTEM_DEFAULT_RUBRIC_NAME)
            evaluation = (await db.execute(select(EvaluationResult).where(EvaluationResult.session_id == session_id))).scalar_one()
            self.assertEqual(evaluation.rubric_version_id, used_rubric_version_id)


if __name__ == "__main__":
    unittest.main()
