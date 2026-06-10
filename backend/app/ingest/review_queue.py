from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewDecision:
    status: str
    reason: str


def precheck_question(title: str, answer_key: str) -> ReviewDecision:
    if len(title.strip()) < 6:
        return ReviewDecision(status="rejected", reason="题目过短")
    if len(answer_key.strip()) < 20:
        return ReviewDecision(status="pending_review", reason="参考答案要点不足")
    return ReviewDecision(status="active", reason="基础检查通过")

