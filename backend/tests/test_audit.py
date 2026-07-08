from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.audit import mask_audit_metadata, record_audit_event
from app.db import get_db
from app.main import app
from app.models import AuditEvent, Base


def _auth_settings(admin_phone_set: set[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        is_production=False,
        auth_dev_code_enabled=True,
        auth_dev_code="000000",
        sms_provider_key="",
        jwt_secret="audit-test-secret",
        access_token_expire_minutes=60,
        admin_phone_set=admin_phone_set or set(),
    )


class _BrokenAuditDb:
    def add(self, _event: AuditEvent) -> None:
        raise RuntimeError("audit insert failed")

    async def commit(self) -> None:
        raise AssertionError("commit should not be reached")

    async def rollback(self) -> None:
        return None


class AuditLogTest(unittest.IsolatedAsyncioTestCase):
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

    async def _login(self, phone: str, request_id: str) -> str:
        with patch("app.api.auth.get_settings", return_value=_auth_settings({"18800000999"})):
            response = await self.client.post(
                "/api/auth/login",
                json={"phone": phone, "code": "000000"},
                headers={"X-Request-ID": request_id},
            )
        self.assertEqual(response.status_code, 200)
        return str(response.json()["access_token"])

    async def _audit_events(self) -> list[AuditEvent]:
        async with self.sessionmaker() as db:
            return (await db.execute(select(AuditEvent).order_by(AuditEvent.id))).scalars().all()

    async def test_login_success_and_failure_write_audit_without_sensitive_values(self) -> None:
        with patch("app.api.auth.get_settings", return_value=_auth_settings()):
            failed = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000001", "code": "123456"},
                headers={"X-Request-ID": "audit-login-failed"},
            )
            success = await self.client.post(
                "/api/auth/login",
                json={"phone": "18800000001", "code": "000000"},
                headers={"X-Request-ID": "audit-login-success"},
            )

        self.assertEqual(failed.status_code, 401)
        self.assertEqual(success.status_code, 200)

        events = await self._audit_events()
        self.assertEqual([event.action for event in events], ["login_failed", "login_success"])
        self.assertEqual([event.request_id for event in events], ["audit-login-failed", "audit-login-success"])
        self.assertEqual(events[0].actor_phone_masked, "188****0001")
        self.assertEqual(events[0].reason, "invalid_code")
        self.assertEqual(events[1].actor_role, "user")
        self.assertIsNotNone(events[1].actor_user_id)

        serialized = json.dumps(
            [
                {
                    "phone": event.actor_phone_masked,
                    "metadata": event.metadata_json,
                    "reason": event.reason,
                }
                for event in events
            ],
            ensure_ascii=False,
        )
        self.assertNotIn("123456", serialized)
        self.assertNotIn("000000", serialized)
        self.assertNotIn("18800000001", serialized)

    async def test_admin_access_and_denied_are_audited_and_admin_can_query(self) -> None:
        admin_token = await self._login("18800000999", "audit-admin-login")
        user_token = await self._login("18800000888", "audit-user-login")

        with patch("app.api.auth.get_settings", return_value=_auth_settings({"18800000999"})):
            denied = await self.client.get(
                "/api/admin/audit-events",
                headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "audit-admin-denied"},
            )
            query_denied = await self.client.get(
                "/api/admin/audit-events?action=admin_denied&status=denied",
                headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "audit-admin-query-denied"},
            )
            query_access = await self.client.get(
                "/api/admin/audit-events?action=admin_access&status=success",
                headers={"Authorization": f"Bearer {admin_token}", "X-Request-ID": "audit-admin-query-access"},
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(query_denied.status_code, 200)
        self.assertEqual(query_access.status_code, 200)

        denied_events = query_denied.json()
        self.assertTrue(any(item["request_id"] == "audit-admin-denied" for item in denied_events))
        self.assertTrue(all(item["action"] == "admin_denied" for item in denied_events))
        self.assertTrue(all(item["status"] == "denied" for item in denied_events))

        access_events = query_access.json()
        self.assertTrue(any(item["request_id"] == "audit-admin-query-denied" for item in access_events))
        self.assertTrue(any(item["request_id"] == "audit-admin-query-access" for item in access_events))

        serialized = json.dumps(denied_events + access_events, ensure_ascii=False)
        self.assertNotIn("18800000999", serialized)
        self.assertNotIn("18800000888", serialized)

    async def test_non_admin_cannot_query_audit_events(self) -> None:
        user_token = await self._login("18800000777", "audit-normal-login")

        with patch("app.api.auth.get_settings", return_value=_auth_settings({"18800000999"})):
            response = await self.client.get(
                "/api/admin/audit-events",
                headers={"Authorization": f"Bearer {user_token}", "X-Request-ID": "audit-normal-denied"},
            )

        self.assertEqual(response.status_code, 403)
        events = await self._audit_events()
        self.assertTrue(any(event.action == "admin_denied" and event.request_id == "audit-normal-denied" for event in events))

    async def test_audit_metadata_masks_sensitive_fields(self) -> None:
        sanitized = mask_audit_metadata(
            {
                "Authorization": "Bearer secret-token",
                "verification_code": "000000",
                "nested": {"prompt_text": "prompt", "safe": "visible"},
                "items": [{"answer": "raw answer", "resource_id": "42"}],
            }
        )

        serialized = json.dumps(sanitized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("000000", serialized)
        self.assertNotIn("raw answer", serialized)
        self.assertEqual(sanitized["Authorization"], "<redacted>")
        self.assertEqual(sanitized["nested"]["safe"], "visible")
        self.assertEqual(sanitized["items"][0]["resource_id"], "42")

    async def test_audit_write_failure_does_not_raise(self) -> None:
        await record_audit_event(  # type: ignore[arg-type]
            _BrokenAuditDb(),
            action="login_success",
            status="success",
            actor_phone="18800000001",
            resource_type="auth",
            request_id="audit-write-failed",
            metadata={"token": "secret"},
        )


if __name__ == "__main__":
    unittest.main()
