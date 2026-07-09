from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Literal

from app.core.llm import ChatMessage, DeepSeekLLM, LLMConfigurationError, LLMResponseError, MockLLM
from app.observability import log_event
from app.settings import Settings, get_settings


LLMFeature = Literal["interview_scoring", "report_generation", "memory_refresh", "rubric_validation", "admin_operation"]
LLMStatus = Literal["success", "failed"]


@dataclass(frozen=True)
class LLMRequest:
    feature: LLMFeature
    messages: Sequence[ChatMessage]
    response_format: str = "json"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: dict[str, Any] | str
    latency_ms: int
    fallback_used: bool = False


@dataclass(frozen=True)
class LLMAttempt:
    provider: str
    model: str
    feature: LLMFeature
    status: LLMStatus
    latency_ms: int
    fallback: bool = False
    error_type: str | None = None


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str


class LLMProvider:
    provider_name = "unknown"

    def __init__(self, model: str, settings: Settings) -> None:
        self.model = model
        self.settings = settings

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        raise NotImplementedError

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    provider_name = "mock"

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        return await MockLLM().json_chat(messages)

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        async for token in MockLLM().stream_chat(messages):
            yield token


class DeepSeekProvider(LLMProvider):
    provider_name = "deepseek"

    def _client(self) -> DeepSeekLLM:
        return DeepSeekLLM(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
            model=self.model,
            timeout_seconds=self.settings.llm_timeout_seconds,
            max_retries=1,
        )

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        return await self._client().json_chat(messages)

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        async for token in self._client().stream_chat(messages):
            yield token


class OpenAICompatibleProvider(DeepSeekProvider):
    provider_name = "openai_compatible"


class ModelRoutePolicy:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def route_for(self, feature: LLMFeature) -> ModelRoute:
        configured = {
            "interview_scoring": self.settings.llm_route_interview_scoring,
            "report_generation": self.settings.llm_route_report_summary,
            "memory_refresh": self.settings.llm_route_memory_refresh,
            "rubric_validation": self.settings.llm_route_rubric_validation,
            "admin_operation": "",
        }.get(feature, "")
        if configured:
            return parse_model_route(configured, self.default_route())
        return self.default_route()

    def default_route(self) -> ModelRoute:
        provider = self.settings.llm_default_provider.strip() or self.settings.llm_provider
        model = self.settings.llm_default_model.strip() or self.settings.deepseek_model
        return ModelRoute(provider=normalize_provider(provider), model=model.strip() or "unknown")

    def fallback_route(self) -> ModelRoute | None:
        if not self.settings.llm_fallback_enabled:
            return None
        provider = self.settings.llm_fallback_provider.strip()
        model = self.settings.llm_fallback_model.strip()
        if not provider or not model:
            return None
        return ModelRoute(provider=normalize_provider(provider), model=model)


class LLMGateway:
    def __init__(self, settings: Settings | None = None, policy: ModelRoutePolicy | None = None) -> None:
        self.settings = settings or get_settings()
        self.policy = policy or ModelRoutePolicy(self.settings)
        self.last_attempts: list[LLMAttempt] = []

    async def call_json(
        self,
        *,
        feature: LLMFeature,
        messages: Sequence[ChatMessage],
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        request = LLMRequest(feature=feature, messages=messages, response_format="json", metadata=metadata or {})
        primary = self.policy.route_for(feature)
        routes = [(primary, False)]
        fallback = self.policy.fallback_route()
        if fallback and fallback != primary:
            routes.append((fallback, True))

        self.last_attempts = []
        last_error: Exception | None = None
        for route, is_fallback in routes:
            for retry_index in range(max(self.settings.llm_max_retries, 1)):
                started_at = perf_counter()
                provider = build_provider(route, self.settings)
                try:
                    raw = await provider.json_chat(request.messages)
                    latency_ms = elapsed_ms(started_at)
                    attempt = LLMAttempt(
                        provider=route.provider,
                        model=route.model,
                        feature=feature,
                        status="success",
                        latency_ms=latency_ms,
                        fallback=is_fallback,
                    )
                    self.last_attempts.append(attempt)
                    log_event(
                        "llm_gateway.call",
                        status="success",
                        feature=feature,
                        provider=route.provider,
                        model=route.model,
                        fallback_used=is_fallback,
                        retry_index=retry_index,
                    )
                    return LLMResponse(
                        provider=route.provider,
                        model=route.model,
                        content=raw,
                        latency_ms=latency_ms,
                        fallback_used=is_fallback,
                    )
                except Exception as exc:  # noqa: BLE001 - provider boundary must normalize all provider errors
                    last_error = exc
                    self.last_attempts.append(
                        LLMAttempt(
                            provider=route.provider,
                            model=route.model,
                            feature=feature,
                            status="failed",
                            latency_ms=elapsed_ms(started_at),
                            fallback=is_fallback,
                            error_type=exc.__class__.__name__,
                        )
                    )
                    log_event(
                        "llm_gateway.call",
                        status="failed",
                        feature=feature,
                        provider=route.provider,
                        model=route.model,
                        fallback_used=is_fallback,
                        retry_index=retry_index,
                        error_type=exc.__class__.__name__,
                    )

        raise LLMResponseError(f"LLM gateway failed for feature={feature}: {last_error}")


class GatewayLLMClient:
    def __init__(self, feature: LLMFeature = "interview_scoring", gateway: LLMGateway | None = None) -> None:
        self.feature = feature
        self.gateway = gateway or LLMGateway()
        route = self.gateway.policy.route_for(feature)
        self.provider = route.provider
        self.model = route.model
        self.last_attempts: list[LLMAttempt] = []
        self.last_response: LLMResponse | None = None

    async def json_chat(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        try:
            response = await self.gateway.call_json(feature=self.feature, messages=messages)
        finally:
            self.last_attempts = list(self.gateway.last_attempts)
        self.last_response = response
        self.provider = response.provider
        self.model = response.model
        if not isinstance(response.content, dict):
            raise LLMResponseError("LLM gateway JSON response must be an object")
        return response.content

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        provider = build_provider(self.gateway.policy.route_for(self.feature), self.gateway.settings)
        async for token in provider.stream_chat(messages):
            yield token


def elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("-", "_")
    if normalized in {"local", "local_fallback", "none"}:
        return "mock"
    if normalized in {"openai", "openai_compatible", "compatible"}:
        return "openai_compatible"
    return normalized or "mock"


def parse_model_route(value: str, default: ModelRoute) -> ModelRoute:
    text = value.strip()
    if not text:
        return default
    if "/" in text:
        provider, model = text.split("/", 1)
    elif ":" in text:
        provider, model = text.split(":", 1)
    else:
        provider, model = default.provider, text
    return ModelRoute(provider=normalize_provider(provider), model=model.strip() or default.model)


def build_provider(route: ModelRoute, settings: Settings) -> LLMProvider:
    if route.provider == "mock":
        return MockLLMProvider(route.model, settings)
    if route.provider == "deepseek":
        return DeepSeekProvider(route.model, settings)
    if route.provider == "openai_compatible":
        return OpenAICompatibleProvider(route.model, settings)
    raise LLMConfigurationError(f"Unsupported LLM provider: {route.provider}")
