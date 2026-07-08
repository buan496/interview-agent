from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import AuditEvent, Base, Question, User
from app.rbac import ROLE_ADMIN, ROLE_CONTENT_OPERATOR


def _auth_settings(admin_phone_set: set[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        is_production=False,
        auth_dev_code_enabled=True,
        auth_dev_code="000000",
        sms_provider_key="",
        jwt_secret="question-bank-test-secret",
        access_token_expire_minutes=60,
        admin_phone_set=admin_phone_set or set(),
    )


class QuestionBankManagementTest(unittest.IsolatedAsyncioTestCase):
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

    def _question_payload(self, title: str = "如何设计 Agent 工具调用的错误恢复机制？") -> dict:
        return {
            "title": title,
            "prompt": "请说明工具调用失败、超时、重试、降级和用户提示的处理策略。",
            "answer_reference": "高质量回答应覆盖超时、重试、幂等、降级、错误分类、用户反馈和可观测性，并说明如何避免无限重试。",
            "difficulty": 3,
            "qtype": "system_design",
            "company_name": "题库管理测试公司",
            "position_name": "ai_agent",
            "tags": ["Agent", "Tool Use"],
        }

    async def test_content_operator_manages_question_lifecycle_and_public_reads_only_published(self) -> None:
        operator_token = await self._login("18800003001")
        await self._set_user_role("18800003001", ROLE_CONTENT_OPERATOR)

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            created = await self.client.post(
                "/api/admin/questions",
                json={**self._question_payload(), "status": "draft"},
                headers={"Authorization": f"Bearer {operator_token}", "X-Request-ID": "qb-create"},
            )
            public_before_publish = await self.client.get("/api/questions")
            detail_before_publish = await self.client.get(f"/api/questions/{created.json()['id']}")
            published = await self.client.post(
                f"/api/admin/questions/{created.json()['id']}/publish",
                headers={"Authorization": f"Bearer {operator_token}", "X-Request-ID": "qb-publish"},
            )
            public_after_publish = await self.client.get("/api/questions")
            archived = await self.client.post(
                f"/api/admin/questions/{created.json()['id']}/archive",
                headers={"Authorization": f"Bearer {operator_token}", "X-Request-ID": "qb-archive"},
            )
            public_after_archive = await self.client.get("/api/questions")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["status"], "draft")
        self.assertEqual(public_before_publish.json()["total"], 0)
        self.assertEqual(detail_before_publish.status_code, 404)
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.json()["status"], "published")
        self.assertEqual(public_after_publish.json()["total"], 1)
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["status"], "archived")
        self.assertEqual(public_after_archive.json()["total"], 0)

        events = await self._audit_events()
        actions = [event.action for event in events]
        self.assertIn("question_created", actions)
        self.assertIn("question_published", actions)
        self.assertIn("question_archived", actions)
        created_event = next(event for event in events if event.action == "question_created")
        self.assertEqual(created_event.request_id, "qb-create")
        self.assertEqual(created_event.actor_role, ROLE_CONTENT_OPERATOR)
        self.assertEqual(created_event.metadata_json["tag_count"], 2)
        self.assertNotIn("answer_reference", created_event.metadata_json)

    async def test_admin_can_update_and_filter_managed_questions(self) -> None:
        admin_token = await self._login("18800003002")
        await self._set_user_role("18800003002", ROLE_ADMIN)

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            created = await self.client.post(
                "/api/admin/questions",
                json={**self._question_payload("如何评估 RAG 系统的答案质量？"), "status": "published"},
                headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "qb-admin-create"},
            )
            question_id = created.json()["id"]
            updated = await self.client.patch(
                f"/api/admin/questions/{question_id}",
                json={"difficulty": 4, "tags": ["RAG", "Evaluation"], "position_name": "llm_engineer"},
                headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "qb-admin-update"},
            )
            by_status = await self.client.get(
                "/api/admin/questions?status=published&tag=RAG&difficulty=4&position=llm_engineer",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            by_wrong_tag = await self.client.get(
                "/api/admin/questions?status=published&tag=Agent",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["difficulty"], 4)
        self.assertEqual([item["name"] for item in updated.json()["tags"]], ["RAG", "Evaluation"])
        self.assertEqual(by_status.status_code, 200)
        self.assertEqual(by_status.json()["total"], 1)
        self.assertEqual(by_wrong_tag.status_code, 200)
        self.assertEqual(by_wrong_tag.json()["total"], 0)

        events = await self._audit_events()
        updated_event = next(event for event in events if event.action == "question_updated")
        self.assertEqual(updated_event.request_id, "qb-admin-update")
        self.assertEqual(set(updated_event.metadata_json["changed_fields"]), {"difficulty", "position_name", "tags"})

    async def test_regular_user_cannot_manage_question_bank_and_content_operator_cannot_query_system_admin(self) -> None:
        user_token = await self._login("18800003003")
        operator_token = await self._login("18800003004")
        await self._set_user_role("18800003004", ROLE_CONTENT_OPERATOR)

        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            denied_create = await self.client.post(
                "/api/admin/questions",
                json=self._question_payload(),
                headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "qb-user-denied"},
            )
            denied_admin = await self.client.get(
                "/api/admin/audit-events",
                headers={"Authorization": f"Bearer {operator_token}", "X-Request-ID": "qb-operator-admin-denied"},
            )

        self.assertEqual(denied_create.status_code, 403)
        self.assertEqual(denied_admin.status_code, 403)
        events = await self._audit_events()
        self.assertTrue(
            any(
                event.action == "question_bank_denied"
                and event.request_id == "qb-user-denied"
                and event.reason == "question_bank_rbac_denied"
                for event in events
            )
        )
        self.assertTrue(
            any(
                event.action == "admin_denied"
                and event.request_id == "qb-operator-admin-denied"
                and event.reason == "content_operator_not_admin"
                for event in events
            )
        )

    async def test_legacy_active_questions_are_public_but_draft_and_archived_are_hidden(self) -> None:
        async with self.sessionmaker() as db:
            db.add_all(
                [
                    Question(
                        id=101,
                        title="Legacy active question",
                        body="legacy",
                        answer_key="legacy answer with enough details for testing",
                        difficulty=2,
                        qtype="knowledge",
                        source_type="curated",
                        status="active",
                    ),
                    Question(
                        id=102,
                        title="Draft question",
                        body="draft",
                        answer_key="draft answer with enough details for testing",
                        difficulty=2,
                        qtype="knowledge",
                        source_type="managed",
                        status="draft",
                    ),
                    Question(
                        id=103,
                        title="Archived question",
                        body="archived",
                        answer_key="archived answer with enough details for testing",
                        difficulty=2,
                        qtype="knowledge",
                        source_type="managed",
                        status="archived",
                    ),
                ]
            )
            await db.commit()

        response = await self.client.get("/api/questions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], 101)

        token = await self._login("18800003005")
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            active_session = await self.client.post(
                "/api/sessions",
                json={"mode": "single", "question_id": 101},
                headers={"Authorization": f"Bearer {token}"},
            )
            draft_session = await self.client.post(
                "/api/sessions",
                json={"mode": "single", "question_id": 102},
                headers={"Authorization": f"Bearer {token}"},
            )
            archived_session = await self.client.post(
                "/api/sessions",
                json={"mode": "single", "question_id": 103},
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(active_session.status_code, 200)
        self.assertEqual(draft_session.status_code, 404)
        self.assertEqual(archived_session.status_code, 404)


if __name__ == "__main__":
    unittest.main()
