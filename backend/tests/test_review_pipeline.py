from __future__ import annotations

import unittest

from app.core.embedding import EmbeddingService
from app.ingest.generator import _fallback_questions
from app.ingest.review_queue import precheck_question


class ReviewPipelineTest(unittest.TestCase):
    def test_precheck_rejects_short_title(self) -> None:
        decision = precheck_question("太短", "这是一个长度足够的参考答案，用于解释核心原理和边界条件。")
        self.assertEqual(decision.status, "rejected")

    def test_fallback_generator_respects_count(self) -> None:
        items = _fallback_questions("负责 Redis、数据库和高并发系统设计", "后端", 4)
        self.assertEqual(len(items), 4)
        self.assertTrue(all(item.answer_key for item in items))
        self.assertTrue(all(1 <= item.difficulty <= 5 for item in items))

    def test_embedding_duplicate_threshold(self) -> None:
        async def run() -> None:
            service = EmbeddingService()
            original = await service.embed_question("Redis 热 key 如何治理？", "请说明监控、拆分和限流。")
            similar = await service.embed_question("Redis 热 key 如何治理？", "请说明监控、拆分和限流。")
            different = await service.embed_question("二叉树层序遍历", "使用队列按层访问节点。")
            duplicate = await service.check_duplicate(original, [(1, similar), (2, different)])
            self.assertTrue(duplicate.is_duplicate)
            self.assertEqual(duplicate.matched_question_id, 1)

        import asyncio

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
