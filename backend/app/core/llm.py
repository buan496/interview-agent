from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.settings import get_settings


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class LLMClient(Protocol):
    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        ...

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        ...


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def _as_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": msg.role, "content": msg.content} for msg in messages]


def parse_json_content(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"LLM did not return valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMResponseError("LLM JSON response must be an object")
    return value


class DeepSeekLLM:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.max_retries = max(max_retries if max_retries is not None else 3, 1)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMConfigurationError("DEEPSEEK_API_KEY is not configured")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": _as_payload(messages),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    raw = response.json()["choices"][0]["message"]["content"]
                    return parse_json_content(raw)
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last_error = exc
                await asyncio.sleep(0.4 * (attempt + 1))
        raise LLMResponseError(f"DeepSeek JSON call failed after retries: {last_error}")

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": _as_payload(messages),
            "temperature": 0.3,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        yield token


class MockLLM:
    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        text = "收到，我会继续按真实面试节奏追问。"
        for char in text:
            yield char
            await asyncio.sleep(0)

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        prompt = messages[-1].content if messages else ""
        answer = prompt.split("候选人最新回答:", 1)[-1].split("当前追问深度:", 1)[0]
        answer = answer.strip()
        depth_text = prompt.split("当前追问深度:", 1)[-1].split("/3", 1)[0].strip()
        try:
            depth = int(depth_text)
        except ValueError:
            depth = 0

        coverage = min(0.92, max(0.18, len(answer) / 240))
        if any(word in answer for word in ("不会", "跳过", "不知道")):
            coverage = 0.05
        if any(word in answer.lower() for word in ("redis", "索引", "复杂度", "一致性", "事务", "缓存")):
            coverage = min(0.88, coverage + 0.25)

        if depth >= 2 or coverage >= 0.82:
            score = int(round(coverage * 100))
            mastery = "pass" if score >= 80 else "weak" if score >= 60 else "fail"
            return {
                "coverage": coverage,
                "correct_points": ["能围绕核心概念作答"],
                "missing_points": ["边界条件和取舍解释还可以更具体"],
                "wrong_points": [],
                "action": "verdict",
                "followup": "",
                "verdict": {
                    "score": score,
                    "mastery": mastery,
                    "feedback": "回答覆盖了部分关键点，建议补充场景、边界条件和方案取舍。",
                    "ideal_answer": "应先定义核心概念，再结合具体场景说明原理、优缺点、边界条件和替代方案。",
                },
            }

        action = "followup_detail" if coverage >= 0.4 else "followup_hint"
        followup = "你提到了这个方向，能结合一个具体场景说明关键步骤和取舍吗？"
        if action == "followup_hint":
            followup = "先不用追求完整答案，你可以从核心概念、典型使用场景和常见问题三个角度展开。"
        return {
            "coverage": coverage,
            "correct_points": [],
            "missing_points": ["需要补充核心要点"],
            "wrong_points": [],
            "action": action,
            "followup": followup,
            "verdict": None,
        }
