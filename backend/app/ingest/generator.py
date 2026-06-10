from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedQuestion:
    title: str
    body: str
    answer_key: str
    qtype: str
    difficulty: int


async def generate_from_jd(jd_text: str, company: str, position: str) -> list[GeneratedQuestion]:
    raise NotImplementedError("Phase 3 will connect this pipeline to the configured LLM provider.")

