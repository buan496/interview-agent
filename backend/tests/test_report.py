from __future__ import annotations

import unittest

from app.api.sessions import _build_report
from app.models import Message, Question, QuestionTag, Session, SessionQuestion, Tag


class ReportBuilderTest(unittest.TestCase):
    def test_builds_score_questions_and_radar(self) -> None:
        tag = Tag(id=1, name="缓存", category="system")
        question = Question(
            id=1,
            title="Redis 为什么快？",
            answer_key="内存访问、事件循环和 IO 多路复用。",
            difficulty=3,
            qtype="knowledge",
            source_type="seed",
        )
        question.tag_links = [QuestionTag(question_id=1, tag_id=1, tag=tag)]
        sq = SessionQuestion(id=1, session_id=1, question_id=1, order_no=1, final_score=80, mastery="pass")
        sq.question = question
        sq.messages = [
            Message(
                id=1,
                sq_id=1,
                role="interviewer",
                content="回答完整。",
                msg_type="verdict",
                eval_json={
                    "verdict": {
                        "feedback": "回答完整。",
                        "ideal_answer": "内存访问、事件循环和 IO 多路复用。",
                    }
                },
            )
        ]
        session = Session(id=1, user_id=1, mode="mock")
        session.questions = [sq]

        report = _build_report(session)

        self.assertEqual(report["overall_score"], 80)
        self.assertEqual(len(report["questions"]), 1)
        self.assertEqual(report["radar"][0]["tag"], "缓存")
        self.assertEqual(report["radar"][0]["avg_score"], 80)


if __name__ == "__main__":
    unittest.main()
