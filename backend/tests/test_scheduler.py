from __future__ import annotations

import unittest

from app.core.scheduler import MOCK_INTERVIEW_MIX, target_question_count, target_type_counts


class SchedulerTest(unittest.TestCase):
    def test_target_question_count(self) -> None:
        self.assertEqual(target_question_count(30), 5)
        self.assertEqual(target_question_count(45), 6)
        self.assertEqual(target_question_count(60), 8)

    def test_type_counts_fill_requested_total(self) -> None:
        counts = target_type_counts(6)
        self.assertEqual(sum(counts.values()), 6)
        self.assertEqual(set(counts), {item.qtype for item in MOCK_INTERVIEW_MIX})
        self.assertGreaterEqual(counts["knowledge"], 2)


if __name__ == "__main__":
    unittest.main()
