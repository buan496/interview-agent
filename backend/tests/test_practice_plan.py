from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from app.api.practice_plan import _compose_tasks, _generated_reason, _plan_out, _weak_tag_task
from app.models import PracticePlan, User


class PracticePlanBuilderTest(unittest.TestCase):
    def test_weak_tag_task_points_to_single_question_with_tag_filter(self) -> None:
        task = _weak_tag_task([{"tag_id": 7, "tag": "Redis", "avg_score": 55, "attempts": 2}])

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["type"], "weak_tag_training")
        self.assertEqual(task["payload"], {"mode": "single", "tag_ids": [7]})

    def test_compose_tasks_keeps_recommendations_actionable(self) -> None:
        user = User(id=1, target_company_id=2, target_position_id=3)
        wrong_task = {
            "id": "wrong-book-review",
            "type": "wrong_book_review",
            "title": "错题复习",
            "reason": "低分题",
            "outcome": "补齐短板",
            "action_label": "重练",
            "entrypoint": "create_session",
            "payload": {"mode": "single", "question_id": 9},
        }

        tasks = _compose_tasks(user, wrong_task, None)

        self.assertEqual([item["type"] for item in tasks], ["wrong_book_review", "mock_interview", "single_question"])
        self.assertEqual(tasks[1]["payload"]["mode"], "mock")
        self.assertEqual(tasks[1]["payload"]["company_id"], 2)

    def test_generated_reason_explains_cold_start(self) -> None:
        reason = _generated_reason(None, None, None)

        self.assertIn("历史数据不足", reason)

    def test_plan_out_validates_task_shape(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        plan = PracticePlan(
            id=1,
            user_id=1,
            plan_date=date(2026, 1, 1),
            recommended_tasks=[
                {
                    "id": "single-question",
                    "type": "single_question",
                    "title": "单题快练",
                    "reason": "建立训练数据",
                    "outcome": "更新画像",
                    "action_label": "开始单题",
                    "entrypoint": "create_session",
                    "payload": {"mode": "single"},
                }
            ],
            weak_tags=[],
            target_abilities=["结构化表达"],
            generated_reason="基于训练记录生成。",
            completed=False,
            created_at=now,
            updated_at=now,
        )

        payload = _plan_out(plan)

        self.assertEqual(payload.id, 1)
        self.assertEqual(payload.recommended_tasks[0].type, "single_question")
        self.assertFalse(payload.completed)


if __name__ == "__main__":
    unittest.main()
