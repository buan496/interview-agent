from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionMix:
    qtype: str
    ratio: float


MOCK_INTERVIEW_MIX: tuple[QuestionMix, ...] = (
    QuestionMix("behavioral", 0.15),
    QuestionMix("knowledge", 0.35),
    QuestionMix("coding", 0.25),
    QuestionMix("system_design", 0.25),
)


def target_question_count(minutes: int = 45) -> int:
    if minutes <= 30:
        return 5
    if minutes >= 60:
        return 8
    return 6

