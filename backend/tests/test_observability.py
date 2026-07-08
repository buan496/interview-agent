from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
import httpx

from app.api.auth import _encode
from app.db import get_db
from app.main import app
from app.models import User
from app.observability import install_observability


class _ReadyDb:
    async def execute(self, _stmt):
        return None


class _ScalarResult:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar_one_or_none(self) -> User | None:
        return self.user


class _UserDb:
    def __init__(self, user: User) -> None:
        self.user = user

    async def execute(self, _stmt):
        return _ScalarResult(self.user)


class ObservabilityTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_response_includes_generated_request_id(self) -> None:
        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("X-Request-ID"))

    async def test_response_preserves_valid_client_request_id(self) -> None:
        response = await self.client.get("/health", headers={"X-Request-ID": "trace-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "trace-123")

    async def test_custom_request_id_header_is_configurable(self) -> None:
        test_app = FastAPI()
        install_observability(
            test_app,
            SimpleNamespace(app_name="Test App", environment="test", log_level="INFO", request_id_header="X-Correlation-ID"),
        )

        @test_app.get("/health")
        async def custom_health() -> dict[str, str]:
            return {"status": "ok"}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://testserver") as client:
            response = await client.get("/health", headers={"X-Correlation-ID": "corr-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Correlation-ID"], "corr-123")

    async def test_health_and_ready_are_available(self) -> None:
        async def override_get_db() -> AsyncIterator[_ReadyDb]:
            yield _ReadyDb()

        app.dependency_overrides[get_db] = override_get_db

        health_response = await self.client.get("/health")
        ready_response = await self.client.get("/ready")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")
        self.assertEqual(ready_response.status_code, 200)
        self.assertEqual(ready_response.json()["status"], "ready")

    async def test_ready_checks_redis_when_required(self) -> None:
        async def override_get_db() -> AsyncIterator[_ReadyDb]:
            yield _ReadyDb()

        app.dependency_overrides[get_db] = override_get_db
        redis_settings = SimpleNamespace(app_name="Interview Agent", environment="test", redis_required=True)

        with (
            patch("app.main.settings", redis_settings),
            patch("app.main.ping_redis", return_value=True) as ping,
        ):
            response = await self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redis"], "ok")
        ping.assert_called_once_with(redis_settings)

    async def test_ready_returns_503_when_required_redis_is_unavailable(self) -> None:
        async def override_get_db() -> AsyncIterator[_ReadyDb]:
            yield _ReadyDb()

        app.dependency_overrides[get_db] = override_get_db
        redis_settings = SimpleNamespace(app_name="Interview Agent", environment="test", redis_required=True)

        with (
            patch("app.main.settings", redis_settings),
            patch("app.main.ping_redis", return_value=False),
        ):
            response = await self.client.get("/ready", headers={"X-Request-ID": "redis-not-ready"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["request_id"], "redis-not-ready")
        self.assertEqual(response.json()["detail"]["redis"], "failed")

    async def test_http_exception_response_contains_request_id(self) -> None:
        response = await self.client.get("/api/auth/me", headers={"X-Request-ID": "missing-auth"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["request_id"], "missing-auth")
        self.assertEqual(response.headers["X-Request-ID"], "missing-auth")

    async def test_unhandled_error_response_contains_request_id(self) -> None:
        test_app = FastAPI()
        install_observability(
            test_app,
            SimpleNamespace(app_name="Test App", environment="test"),
        )

        @test_app.get("/boom")
        async def boom() -> dict[str, str]:
            raise RuntimeError("internal failure")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/boom", headers={"X-Request-ID": "boom-1"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["X-Request-ID"], "boom-1")
        self.assertEqual(response.json(), {"detail": "Internal Server Error", "request_id": "boom-1"})

    async def test_request_log_does_not_include_authorization_token(self) -> None:
        token = "secret-token-that-must-not-appear"

        with self.assertLogs("interview_agent", level="INFO") as logs:
            response = await self.client.get(
                "/health",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "safe-log-1"},
            )

        self.assertEqual(response.status_code, 200)
        log_text = "\n".join(logs.output)
        self.assertIn("safe-log-1", log_text)
        self.assertIn("http_request", log_text)
        self.assertNotIn(token, log_text)
        self.assertNotIn("Authorization", log_text)

    async def test_request_log_includes_user_id_when_available(self) -> None:
        test_app = FastAPI()
        install_observability(
            test_app,
            SimpleNamespace(app_name="Test App", environment="test"),
        )

        @test_app.get("/current")
        async def current(request: Request) -> dict[str, bool]:
            request.state.user_id = 42
            return {"ok": True}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://testserver") as client:
            with self.assertLogs("interview_agent", level="INFO") as logs:
                response = await client.get("/current", headers={"X-Request-ID": "user-log-1"})

        self.assertEqual(response.status_code, 200)
        log_text = "\n".join(logs.output)
        self.assertIn("user-log-1", log_text)
        self.assertIn('"user_id": 42', log_text)

    async def test_authenticated_request_log_includes_current_user_id(self) -> None:
        user = User(id=42, phone="13800000000")

        async def override_get_db() -> AsyncIterator[_UserDb]:
            yield _UserDb(user)

        app.dependency_overrides[get_db] = override_get_db
        token = _encode({"sub": "13800000000", "uid": 42, "exp": int(time.time()) + 60})

        with self.assertLogs("interview_agent", level="INFO") as logs:
            response = await self.client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}", "X-Request-ID": "auth-user-42"},
            )

        self.assertEqual(response.status_code, 200)
        log_text = "\n".join(logs.output)
        self.assertIn("auth-user-42", log_text)
        self.assertIn('"user_id": 42', log_text)


if __name__ == "__main__":
    unittest.main()
