from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from fastapi import HTTPException

from app.api.sessions import _assert_answerable, _expire_if_needed, _remaining_seconds, _session_duration
from app.models import Session, SessionQuestion


class SessionStateTest(unittest.TestCase):
    def test_session_duration_by_mode(self) -> None:
        self.assertEqual(_session_duration("single"), timedelta(minutes=20))
        self.assertEqual(_session_duration("mock"), timedelta(minutes=45))

    def test_remaining_seconds_uses_deadline(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session = Session(id=1, user_id=1, mode="mock", status="ongoing")
        session.deadline_at = now + timedelta(seconds=90)
        self.assertEqual(_remaining_seconds(session, now), 90)

    def test_expire_marks_session_and_open_questions(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session = Session(id=1, user_id=1, mode="mock", status="ongoing")
        session.deadline_at = now - timedelta(seconds=1)
        pending = SessionQuestion(id=1, session_id=1, question_id=1, order_no=1, status="answering")
        scored = SessionQuestion(id=2, session_id=1, question_id=2, order_no=2, status="scored")
        session.questions = [pending, scored]

        self.assertTrue(_expire_if_needed(session, now))
        self.assertEqual(session.status, "expired")
        self.assertEqual(session.end_reason, "timeout")
        self.assertEqual(pending.status, "timeout")
        self.assertEqual(scored.status, "scored")

    def test_assert_answerable_rejects_finished(self) -> None:
        session = Session(id=1, user_id=1, mode="single", status="finished")
        session.deadline_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.questions = []
        with self.assertRaises(HTTPException):
            _assert_answerable(session, datetime(2025, 1, 1, tzinfo=timezone.utc))

    def test_assert_answerable_rejects_expired(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session = Session(id=1, user_id=1, mode="single", status="ongoing")
        session.deadline_at = now - timedelta(seconds=1)
        session.questions = []
        with self.assertRaises(HTTPException):
            _assert_answerable(session, now)
        self.assertEqual(session.status, "expired")


if __name__ == "__main__":
    unittest.main()
