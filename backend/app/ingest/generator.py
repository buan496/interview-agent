from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.llm import ChatMessage, DeepSeekLLM, LLMConfigurationError, LLMResponseError


@dataclass(frozen=True)
class GeneratedQuestion:
    title: str
    body: str
    answer_key: str
    qtype: str
    difficulty: int


def _normalize_item(item: dict[str, Any]) -> GeneratedQuestion:
    qtype = str(item.get("qtype") or "knowledge")
    if qtype not in {"behavioral", "knowledge", "coding", "system_design"}:
        qtype = "knowledge"
    try:
        difficulty = max(1, min(5, int(item.get("difficulty") or 3)))
    except (TypeError, ValueError):
        difficulty = 3
    return GeneratedQuestion(
        title=str(item.get("title") or "请介绍该岗位的一项核心技术能力。")[:300],
        body=str(item.get("body") or ""),
        answer_key=str(item.get("answer_key") or "回答应覆盖核心概念、实践场景、方案取舍和边界条件。"),
        qtype=qtype,
        difficulty=difficulty,
    )


def _fallback_questions(jd_text: str, position: str, count: int) -> list[GeneratedQuestion]:
    focus = "、".join(
        token
        for token in ("高并发", "数据库", "缓存", "系统设计", "算法", "前端性能", "项目协作")
        if token in jd_text
    ) or "岗位核心技术"
    templates = (
        ("请结合项目经历说明你如何应用{focus}。", "behavioral", 3),
        ("针对{focus}，你会如何设计一个可上线的技术方案？", "system_design", 4),
        ("请解释{focus}中的关键原理、常见问题和排查方法。", "knowledge", 3),
        ("如果业务规模扩大 10 倍，{focus}方案需要怎样调整？", "system_design", 4),
        ("请描述一个与{focus}相关的故障，以及你的定位和复盘过程。", "behavioral", 3),
    )
    result = []
    for index in range(count):
        title, qtype, difficulty = templates[index % len(templates)]
        result.append(
            GeneratedQuestion(
                title=title.format(focus=focus),
                body=f"目标岗位：{position}。请给出结构化回答。",
                answer_key="回答应明确背景和目标，说明核心原理、实施步骤、关键指标、边界条件、风险与替代方案，并给出可验证的结果。",
                qtype=qtype,
                difficulty=difficulty,
            )
        )
    return result


async def generate_from_jd(
    jd_text: str,
    company: str,
    position: str,
    count: int = 5,
) -> list[GeneratedQuestion]:
    prompt = f"""根据以下招聘 JD 为 {company} 的 {position} 岗位生成 {count} 道中文面试题。
题目需覆盖知识、项目行为、编码思路或系统设计，禁止照抄 JD。
JD:
{jd_text}

只输出 JSON 对象:
{{"items":[{{"title":"...","body":"...","answer_key":"至少100字的评分要点","qtype":"behavioral|knowledge|coding|system_design","difficulty":1}}]}}
"""
    try:
        raw = await DeepSeekLLM().json_chat([ChatMessage(role="system", content=prompt)])
        items = raw.get("items")
        if not isinstance(items, list) or not items:
            raise LLMResponseError("Generator response did not include items")
        return [_normalize_item(item) for item in items[:count] if isinstance(item, dict)]
    except (LLMConfigurationError, LLMResponseError):
        return _fallback_questions(jd_text, position, count)
