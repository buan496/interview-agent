from __future__ import annotations

import time
import unittest

from fastapi import HTTPException

from app.api.auth import _decode, _encode


class AuthTokenTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        self.assertEqual(_decode(token)["sub"], "13800000000")

    def test_rejects_tampered_token(self) -> None:
        token = _encode({"sub": "13800000000", "exp": int(time.time()) + 60})
        with self.assertRaises(HTTPException):
            _decode(f"{token}tampered")


if __name__ == "__main__":
    unittest.main()
