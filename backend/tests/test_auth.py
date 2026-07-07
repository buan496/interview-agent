from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.auth import (
    LoginRequest,
    RequestCodeRequest,
    _bearer_token,
    _decode,
    _encode,
    _get_or_create_user,
    get_current_user,
    login,
    request_code,
    require_admin,
    verify_sms_code,
)
from app.models import User


class _ScalarResult:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar_one_or_none(self) -> User | None:
        return self.user


class _FakeDb:
    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.added: list[User] = []
        self.committed = False
        self.refreshed: User | None = None

    async def execute(self, _stmt):
        return _ScalarResult(self.user)

    def add(self, user: User) -> None:
        self.added.append(user)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, user: User) -> None:
        if user.id is None:
            user.id = 1
        self.refreshed = user


def _auth_settings(
    *,
    environment: str = "development",
    auth_dev_code_enabled: bool = True,
    auth_dev_code: str = "000000",
    sms_provider_key: str = "",
    jwt_secret: str = "test-secret",
    access_token_expire_minutes: int = 60,
    admin_phone_set: set[str] | None = None,
):
    return SimpleNamespace(
        environment=environment,
        is_production=environment in {"prod", "production"},
        auth_dev_code_enabled=auth_dev_code_enabled,
        auth_dev_code=auth_dev_code,
        sms_provider_key=sms_provider_key,
        jwt_secret=jwt_secret,
        access_token_expire_minutes=access_token_expire_minutes,
        admin_phone_set=admin_phone_set or set(),
    )


class AuthTokenTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        self.assertEqual(_decode(token)["sub"], "13800000000")

    def test_rejects_tampered_token(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        with self.assertRaises(HTTPException):
            _decode(f"{token}tampered")

    def test_rejects_expired_token(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) - 1})
        with self.assertRaises(HTTPException):
            _decode(token)

    def test_requires_bearer_token(self) -> None:
        self.assertEqual(_bearer_token("Bearer abc"), "abc")
        with self.assertRaises(HTTPException):
            _bearer_token(None)

    def test_current_user_resolves_from_bearer_token(self) -> None:
        async def run() -> None:
            token = _encode({"sub": "13800000000", "uid": 1, "exp": int(time.time()) + 60})
            user = User(id=1, phone="13800000000")
            result = await get_current_user(f"Bearer {token}", _FakeDb(user))  # type: ignore[arg-type]
            self.assertIs(result, user)

        import asyncio

        asyncio.run(run())

    def test_get_or_create_user_reuses_existing_user(self) -> None:
        async def run() -> None:
            user = User(id=1, phone="13800000000")
            db = _FakeDb(user)
            result = await _get_or_create_user(db, "13800000000")  # type: ignore[arg-type]
            self.assertIs(result, user)
            self.assertFalse(db.added)
            self.assertFalse(db.committed)

        import asyncio

        asyncio.run(run())

    def test_get_or_create_user_persists_new_user(self) -> None:
        async def run() -> None:
            db = _FakeDb()
            result = await _get_or_create_user(db, "13800000000")  # type: ignore[arg-type]
            self.assertEqual(result.phone, "13800000000")
            self.assertEqual(len(db.added), 1)
            self.assertTrue(db.committed)
            self.assertIs(db.refreshed, result)

        import asyncio

        asyncio.run(run())

    def test_dev_code_verifier_accepts_configured_code(self) -> None:
        settings = _auth_settings(auth_dev_code="123456")

        self.assertTrue(verify_sms_code("13800000000", "123456", settings))  # type: ignore[arg-type]
        self.assertFalse(verify_sms_code("13800000000", "000000", settings))  # type: ignore[arg-type]

    def test_request_code_returns_dev_code_only_in_non_production(self) -> None:
        async def run() -> None:
            with patch("app.api.auth.get_settings", return_value=_auth_settings(auth_dev_code="123456")):
                response = await request_code(RequestCodeRequest(phone="13800000000"))
                self.assertEqual(response["development_code"], "123456")

        import asyncio

        asyncio.run(run())

    def test_production_rejects_default_dev_code(self) -> None:
        async def run() -> None:
            settings = _auth_settings(environment="production", jwt_secret="prod-secret", auth_dev_code_enabled=True, auth_dev_code="000000")
            with patch("app.api.auth.get_settings", return_value=settings):
                with self.assertRaises(HTTPException) as ctx:
                    await request_code(RequestCodeRequest(phone="13800000000"))
                self.assertEqual(ctx.exception.status_code, 500)

        import asyncio

        asyncio.run(run())

    def test_production_requires_sms_provider_when_dev_code_disabled(self) -> None:
        async def run() -> None:
            settings = _auth_settings(environment="production", jwt_secret="prod-secret", auth_dev_code_enabled=False, sms_provider_key="")
            with patch("app.api.auth.get_settings", return_value=settings):
                with self.assertRaises(HTTPException) as ctx:
                    await request_code(RequestCodeRequest(phone="13800000000"))
                self.assertEqual(ctx.exception.status_code, 503)

        import asyncio

        asyncio.run(run())

    def test_production_rejects_default_jwt_secret(self) -> None:
        settings = _auth_settings(environment="production", jwt_secret="local-dev-only-change-me", auth_dev_code="654321")

        with self.assertRaises(HTTPException):
            verify_sms_code("13800000000", "654321", settings)  # type: ignore[arg-type]

    def test_login_accepts_dev_code_and_uses_configured_expiry(self) -> None:
        async def run() -> None:
            settings = _auth_settings(auth_dev_code="123456", access_token_expire_minutes=5)
            db = _FakeDb(User(id=7, phone="13800000000"))
            with patch("app.api.auth.get_settings", return_value=settings):
                response = await login(LoginRequest(phone="13800000000", code="123456"), db)  # type: ignore[arg-type]
                self.assertEqual(response["expires_in"], 300)
                payload = _decode(str(response["access_token"]))
                self.assertEqual(payload["sub"], "13800000000")
                self.assertEqual(payload["uid"], 7)

        import asyncio

        asyncio.run(run())

    def test_login_rejects_wrong_code(self) -> None:
        async def run() -> None:
            with patch("app.api.auth.get_settings", return_value=_auth_settings(auth_dev_code="123456")):
                with self.assertRaises(HTTPException) as ctx:
                    await login(LoginRequest(phone="13800000000", code="000000"), _FakeDb())  # type: ignore[arg-type]
                self.assertEqual(ctx.exception.status_code, 401)

        import asyncio

        asyncio.run(run())

    def test_require_admin_allows_configured_phone(self) -> None:
        async def run() -> None:
            with patch("app.api.auth.get_settings", return_value=SimpleNamespace(admin_phone_set={"13800000000"})):
                user = User(id=1, phone="13800000000")
                self.assertIs(await require_admin(user), user)

        import asyncio

        asyncio.run(run())

    def test_require_admin_rejects_normal_user(self) -> None:
        async def run() -> None:
            with patch("app.api.auth.get_settings", return_value=SimpleNamespace(admin_phone_set={"13800000000"})):
                with self.assertRaises(HTTPException):
                    await require_admin(User(id=2, phone="13900000000"))

        import asyncio

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
