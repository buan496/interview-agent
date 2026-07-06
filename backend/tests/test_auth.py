from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.auth import _bearer_token, _decode, _encode, _get_or_create_user, require_admin
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
        self.refreshed = user


class AuthTokenTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        self.assertEqual(_decode(token)["sub"], "13800000000")

    def test_rejects_tampered_token(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        with self.assertRaises(HTTPException):
            _decode(f"{token}tampered")

    def test_requires_bearer_token(self) -> None:
        self.assertEqual(_bearer_token("Bearer abc"), "abc")
        with self.assertRaises(HTTPException):
            _bearer_token(None)

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
