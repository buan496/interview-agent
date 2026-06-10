from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DuplicateCheckResult:
    is_duplicate: bool
    matched_question_id: int | None = None
    similarity: float = 0.0


class EmbeddingService:
    async def embed_question(self, title: str, body: str | None = None) -> list[float]:
        text = f"{title}\n{body or ''}".strip()
        if not text:
            return [0.0] * 1024
        vector = [0.0] * 1024
        normalized = "".join(text.lower().split())
        grams = [normalized[index : index + 3] for index in range(max(1, len(normalized) - 2))]
        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % len(vector)
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def check_duplicate(
        self,
        embedding: list[float],
        candidates: Iterable[tuple[int, list[float]]] = (),
        threshold: float = 0.92,
    ) -> DuplicateCheckResult:
        best_id: int | None = None
        best_similarity = 0.0
        for question_id, candidate in candidates:
            similarity = cosine_similarity(embedding, candidate)
            if similarity > best_similarity:
                best_id = question_id
                best_similarity = similarity
        return DuplicateCheckResult(
            is_duplicate=best_similarity >= threshold,
            matched_question_id=best_id if best_similarity >= threshold else None,
            similarity=best_similarity,
        )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
