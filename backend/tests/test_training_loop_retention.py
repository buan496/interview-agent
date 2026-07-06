from __future__ import annotations

from datetime import date
from decimal import Decimal
import unittest

from app.api.sessions import _update_retention_tables
from app.models import Question, QuestionTag, Session, SessionQuestion, Tag, UserTagStat, WrongBook


class FakeRetentionDb:
    def __init__(self) -> None:
        self.wrong_book: dict[tuple[int, int], WrongBook] = {}
        self.tag_stats: dict[tuple[int, int], UserTagStat] = {}

    async def get(self, model, key):
        lookup_key = (key["user_id"], key["question_id"] if model is WrongBook else key["tag_id"])
        if model is WrongBook:
            return self.wrong_book.get(lookup_key)
        if model is UserTagStat:
            return self.tag_stats.get(lookup_key)
        raise AssertionError(f"Unexpected model lookup: {model}")

    def add(self, item) -> None:
        if isinstance(item, WrongBook):
            self.wrong_book[(item.user_id, item.question_id)] = item
            return
        if isinstance(item, UserTagStat):
            self.tag_stats[(item.user_id, item.tag_id)] = item
            return
        raise AssertionError(f"Unexpected added item: {item!r}")


def session_question_with_tags(*tag_ids: int) -> tuple[Session, SessionQuestion]:
    tags = [Tag(id=tag_id, name=f"Tag {tag_id}", category="knowledge") for tag_id in tag_ids]
    question = Question(
        id=100,
        title="Why is Redis fast?",
        answer_key="Cover memory, event loop, IO multiplexing, and data structures.",
        difficulty=3,
        qtype="knowledge",
        source_type="seed",
    )
    question.tag_links = [QuestionTag(question_id=100, tag_id=tag.id, tag=tag) for tag in tags]
    sq = SessionQuestion(id=10, session_id=42, question_id=100, order_no=1)
    sq.question = question
    session = Session(id=42, user_id=7, mode="single")
    return session, sq


class TrainingLoopRetentionTest(unittest.IsolatedAsyncioTestCase):
    async def test_weak_result_updates_wrong_book_and_tag_stats(self) -> None:
        db = FakeRetentionDb()
        session, sq = session_question_with_tags(1, 2)

        await _update_retention_tables(db, session, sq, score=62, mastery="weak", today=date(2026, 7, 6))

        wrong = db.wrong_book[(7, 100)]
        self.assertEqual(wrong.last_score, 62)
        self.assertEqual(wrong.fail_count, 1)
        self.assertEqual(wrong.next_review, date(2026, 7, 7))
        self.assertEqual(db.tag_stats[(7, 1)].attempts, 1)
        self.assertEqual(db.tag_stats[(7, 1)].avg_score, 62)
        self.assertEqual(db.tag_stats[(7, 2)].attempts, 1)
        self.assertEqual(db.tag_stats[(7, 2)].avg_score, 62)

    async def test_repeated_failure_increments_review_interval_and_rolling_average(self) -> None:
        db = FakeRetentionDb()
        session, sq = session_question_with_tags(1)
        db.wrong_book[(7, 100)] = WrongBook(user_id=7, question_id=100, last_score=58, fail_count=1, next_review=date(2026, 7, 7))
        db.tag_stats[(7, 1)] = UserTagStat(user_id=7, tag_id=1, attempts=2, avg_score=Decimal("60.00"))

        await _update_retention_tables(db, session, sq, score=75, mastery="fail", today=date(2026, 7, 6))

        wrong = db.wrong_book[(7, 100)]
        self.assertEqual(wrong.last_score, 75)
        self.assertEqual(wrong.fail_count, 2)
        self.assertEqual(wrong.next_review, date(2026, 7, 9))
        self.assertEqual(db.tag_stats[(7, 1)].attempts, 3)
        self.assertEqual(db.tag_stats[(7, 1)].avg_score, Decimal("65.00"))

    async def test_passing_result_updates_ability_without_wrong_book_entry(self) -> None:
        db = FakeRetentionDb()
        session, sq = session_question_with_tags(1)

        await _update_retention_tables(db, session, sq, score=88, mastery="pass", today=date(2026, 7, 6))

        self.assertNotIn((7, 100), db.wrong_book)
        self.assertEqual(db.tag_stats[(7, 1)].attempts, 1)
        self.assertEqual(db.tag_stats[(7, 1)].avg_score, 88)


if __name__ == "__main__":
    unittest.main()
