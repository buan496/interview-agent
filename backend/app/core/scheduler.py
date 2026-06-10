from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle


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


def target_type_counts(total: int) -> dict[str, int]:
    counts = {item.qtype: int(total * item.ratio) for item in MOCK_INTERVIEW_MIX}
    assigned = sum(counts.values())
    for item in cycle(MOCK_INTERVIEW_MIX):
        if assigned >= total:
            break
        counts[item.qtype] += 1
        assigned += 1
    return counts
