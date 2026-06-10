from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicateCheckResult:
    is_duplicate: bool
    matched_question_id: int | None = None
    similarity: float = 0.0


class EmbeddingService:
    async def embed_question(self, title: str, body: str | None = None) -> list[float]:
        # The concrete provider is intentionally isolated for Phase 3.
        text = f"{title}\n{body or ''}".strip()
        if not text:
            return [0.0] * 1024
        seed = sum(ord(ch) for ch in text)
        return [((seed + idx * 31) % 997) / 997 for idx in range(1024)]

    async def check_duplicate(self, embedding: list[float]) -> DuplicateCheckResult:
        return DuplicateCheckResult(is_duplicate=False)

