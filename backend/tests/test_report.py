from __future__ import annotations

import unittest

from app.api.sessions import _build_report, _evaluation_result_row
from app.core.interviewer import EvaluationResult as EngineEvaluationResult
from app.core.interviewer import Verdict
from app.models import EvaluationResult, Message, Question, QuestionTag, ScoringRubricVersion, Session, SessionQuestion, Tag


class ReportBuilderTest(unittest.TestCase):
    def test_builds_score_questions_and_radar_from_message_fallback(self) -> None:
        tag = Tag(id=1, name="Redis", category="knowledge")
        question = Question(
            id=1,
            title="Why is Redis fast?",
            answer_key="memory, event loop, io multiplexing",
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
                content="Solid answer.",
                msg_type="verdict",
                eval_json={
                    "correct_points": ["memory access"],
                    "missing_points": ["io multiplexing"],
                    "wrong_points": [],
                    "verdict": {
                        "feedback": "Solid answer.",
                        "ideal_answer": "Use memory, event loop, and IO multiplexing.",
                    },
                },
            )
        ]
        session = Session(id=1, user_id=1, mode="mock")
        session.questions = [sq]

        report = _build_report(session)

        self.assertEqual(report["overall_score"], 80)
        self.assertEqual(len(report["questions"]), 1)
        self.assertEqual(report["radar"][0]["tag"], "Redis")
        self.assertEqual(report["radar"][0]["avg_score"], 80)
        self.assertEqual(report["questions"][0]["missing_points"], ["io multiplexing"])

    def test_report_prefers_persisted_evaluation_result(self) -> None:
        tag = Tag(id=1, name="Redis", category="knowledge")
        question = Question(
            id=1,
            title="Why is Redis fast?",
            answer_key="memory, event loop, io multiplexing",
            difficulty=3,
            qtype="knowledge",
            source_type="seed",
        )
        question.tag_links = [QuestionTag(question_id=1, tag_id=1, tag=tag)]
        sq = SessionQuestion(id=1, session_id=1, question_id=1, order_no=1, final_score=72, mastery="weak")
        sq.question = question
        sq.messages = []
        sq.evaluation_results = [
            EvaluationResult(
                id=1,
                user_id=1,
                session_id=1,
                sq_id=1,
                question_id=1,
                score=72,
                mastery="weak",
                verdict="Good structure, missing IO details.",
                strengths=["clear opening"],
                missing_points=["IO multiplexing"],
                expression_issues=["too abstract"],
                action_items=["Review and restate: IO multiplexing"],
                recommended_questions=[],
                raw_model_output={"verdict": {"ideal_answer": "Use memory and IO multiplexing."}},
                model_name="mock-model",
                prompt_version="interviewer-v1",
            )
        ]
        session = Session(id=1, user_id=1, mode="single")
        session.questions = [sq]

        report = _build_report(session)
        item = report["questions"][0]

        self.assertEqual(item["feedback"], "Good structure, missing IO details.")
        self.assertEqual(item["ideal_answer"], "Use memory and IO multiplexing.")
        self.assertEqual(item["missing_points"], ["IO multiplexing"])
        self.assertEqual(item["action_items"], ["Review and restate: IO multiplexing"])

    def test_evaluation_result_row_binds_user_session_and_question(self) -> None:
        session = Session(id=9, user_id=3, mode="single")
        sq = SessionQuestion(id=10, session_id=9, question_id=11, order_no=1)
        result = EngineEvaluationResult(
            coverage=0.7,
            correct_points=["named memory access"],
            missing_points=["event loop"],
            wrong_points=["claimed multi-threading"],
            action="verdict",
            verdict=Verdict(score=70, mastery="weak", feedback="Needs event loop detail.", ideal_answer="Mention event loop."),
        )

        rubric_version = ScoringRubricVersion(
            id=42,
            rubric_id=7,
            version="v1",
            dimensions_json=[{"key": "correctness", "weight": 100}],
            prompt_template="Score with a test rubric.",
            scoring_scale="0-100",
            status="published",
        )

        row = _evaluation_result_row(session, sq, result, "mock-model", rubric_version)

        self.assertEqual(row.user_id, 3)
        self.assertEqual(row.session_id, 9)
        self.assertEqual(row.sq_id, 10)
        self.assertEqual(row.question_id, 11)
        self.assertEqual(row.score, 70)
        self.assertEqual(row.missing_points, ["event loop"])
        self.assertEqual(row.expression_issues, ["claimed multi-threading"])
        self.assertEqual(row.model_name, "mock-model")
        self.assertEqual(row.rubric_version_id, 42)
        self.assertEqual(row.raw_model_output["rubric"]["version"], "v1")


if __name__ == "__main__":
    unittest.main()
