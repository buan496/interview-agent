from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interviewer import ConversationMessage, EvaluationResult, InterviewQuestion
from app.metrics import record_llm_usage_metrics
from app.models import LLMUsageRecord
from app.observability import get_request_id, log_event
from app.settings import DEFAULT_LLM_PRICING_VERSION, Settings, get_settings


LLM_PRICING_VERSION = DEFAULT_LLM_PRICING_VERSION
USD_QUANT = Decimal("0.000001")

UsageFeature = Literal[
    "scoring",
    "follow_up",
    "report",
    "mock",
    "ability",
    "interview_scoring",
    "report_generation",
    "memory_refresh",
    "rubric_validation",
    "admin_operation",
    "unknown",
]
UsageStatus = Literal["success", "failed"]


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal


MODEL_PRICES: dict[tuple[str, str], ModelPrice] = {
    ("deepseek", "deepseek-chat"): ModelPrice(Decimal("0.270000"), Decimal("1.100000")),
    ("deepseek", "deepseek-reasoner"): ModelPrice(Decimal("0.550000"), Decimal("2.190000")),
    ("mock", "local-fallback"): ModelPrice(Decimal("0.000000"), Decimal("0.000000")),
}


def calculate_estimated_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> Decimal:
    price = MODEL_PRICES.get((provider, model))
    if price is None:
        return Decimal("0.000000")
    input_cost = (Decimal(max(prompt_tokens, 0)) / Decimal(1_000_000)) * price.input_per_million
    output_cost = (Decimal(max(completion_tokens, 0)) / Decimal(1_000_000)) * price.output_per_million
    return (input_cost + output_cost).quantize(USD_QUANT, rounding=ROUND_HALF_UP)


def pricing_version(settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    return active_settings.llm_pricing_version or LLM_PRICING_VERSION


def usage_metering_enabled(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return active_settings.llm_usage_metering_enabled


def estimate_text_tokens(value: str | None) -> int:
    if not value:
        return 0
    # Lightweight v1 estimate. The raw text is never stored in the usage ledger.
    return max(1, (len(value.strip()) + 3) // 4)


def estimate_prompt_tokens(question: InterviewQuestion, history: Iterable[ConversationMessage], answer: str, depth: int) -> int:
    total = estimate_text_tokens(question.title)
    total += estimate_text_tokens(question.answer_key)
    total += estimate_text_tokens(question.company)
    total += estimate_text_tokens(question.position)
    total += estimate_text_tokens(str(depth))
    for message in history:
        total += estimate_text_tokens(message.role)
        total += estimate_text_tokens(message.msg_type)
        total += estimate_text_tokens(message.content)
    total += estimate_text_tokens(answer)
    return total


def estimate_completion_tokens(result: EvaluationResult | None) -> int:
    if result is None:
        return 0
    total = estimate_text_tokens(result.action)
    total += estimate_text_tokens(result.followup)
    for item in [*result.correct_points, *result.missing_points, *result.wrong_points]:
        total += estimate_text_tokens(item)
    if result.verdict:
        total += estimate_text_tokens(result.verdict.feedback)
        total += estimate_text_tokens(result.verdict.ideal_answer)
        total += estimate_text_tokens(result.verdict.mastery)
        total += estimate_text_tokens(str(result.verdict.score))
    return total


def provider_from_llm(llm: Any) -> str:
    provider = getattr(llm, "provider", None)
    if provider:
        return str(provider)
    name = llm.__class__.__name__.lower()
    if "deepseek" in name:
        return "deepseek"
    if "mock" in name:
        return "mock"
    return "unknown"


def model_from_llm(llm: Any) -> str:
    return str(getattr(llm, "model", "local-fallback") or "unknown")


def feature_from_result(result: EvaluationResult | None) -> UsageFeature:
    if result is None:
        return "unknown"
    if result.action == "verdict":
        return "scoring"
    return "follow_up"


def elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


async def record_llm_usage(
    db: AsyncSession,
    *,
    user_id: int,
    session_id: int | None,
    feature: UsageFeature,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int | None,
    status: UsageStatus,
    error_type: str | None = None,
    request_id: str | None = None,
) -> LLMUsageRecord:
    prompt_token_count = max(prompt_tokens, 0)
    completion_token_count = max(completion_tokens, 0)
    record = LLMUsageRecord(
        user_id=user_id,
        session_id=session_id,
        request_id=request_id or get_request_id(),
        feature=feature,
        provider=provider,
        model=model,
        prompt_tokens=prompt_token_count,
        completion_tokens=completion_token_count,
        total_tokens=prompt_token_count + completion_token_count,
        estimated_cost=calculate_estimated_cost(provider, model, prompt_token_count, completion_token_count),
        currency="USD",
        pricing_version=pricing_version(),
        latency_ms=latency_ms,
        status=status,
        error_type=error_type,
    )
    db.add(record)
    await db.flush()
    log_event(
        "llm_call_failed" if status == "failed" else "llm_usage_recorded",
        status=status,
        user_id=user_id,
        session_id=session_id,
        feature=feature,
        provider=provider,
        model=model,
        total_tokens=record.total_tokens,
        estimated_cost=str(record.estimated_cost),
        latency_ms=latency_ms,
        error_type=error_type,
    )
    record_llm_usage_metrics(
        provider=provider,
        model=model,
        feature=feature,
        status=status,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        estimated_cost=record.estimated_cost,
        currency=record.currency,
        latency_ms=latency_ms,
    )
    return record


def _month_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _empty_summary() -> dict[str, Any]:
    return {
        "total_tokens": 0,
        "total_estimated_cost": Decimal("0.000000"),
        "current_month_tokens": 0,
        "current_month_estimated_cost": Decimal("0.000000"),
        "currency": "USD",
        "pricing_version": pricing_version(),
        "by_feature": [],
        "by_model": [],
        "recent_records": [],
    }


async def get_user_usage_summary(db: AsyncSession, user_id: int) -> dict[str, Any]:
    records = (
        await db.execute(
            select(LLMUsageRecord)
            .where(LLMUsageRecord.user_id == user_id)
            .order_by(LLMUsageRecord.created_at.desc(), LLMUsageRecord.id.desc())
        )
    ).scalars().all()
    if not records:
        return _empty_summary()

    month_start = _month_start_utc()
    total_tokens = sum(item.total_tokens for item in records)
    total_cost = sum((item.estimated_cost for item in records), Decimal("0.000000"))
    monthly_records = [item for item in records if (created_at := _as_utc(item.created_at)) and created_at >= month_start]
    current_month_tokens = sum(item.total_tokens for item in monthly_records)
    current_month_cost = sum((item.estimated_cost for item in monthly_records), Decimal("0.000000"))

    feature_groups: dict[str, list[LLMUsageRecord]] = defaultdict(list)
    model_groups: dict[str, list[LLMUsageRecord]] = defaultdict(list)
    for record in records:
        feature_groups[record.feature].append(record)
        model_groups[f"{record.provider}/{record.model}"].append(record)

    def breakdown(key: str, items: list[LLMUsageRecord]) -> dict[str, Any]:
        return {
            "key": key,
            "call_count": len(items),
            "failed_count": sum(1 for item in items if item.status == "failed"),
            "total_tokens": sum(item.total_tokens for item in items),
            "estimated_cost": sum((item.estimated_cost for item in items), Decimal("0.000000")),
        }

    return {
        "total_tokens": total_tokens,
        "total_estimated_cost": total_cost.quantize(USD_QUANT),
        "current_month_tokens": current_month_tokens,
        "current_month_estimated_cost": current_month_cost.quantize(USD_QUANT),
        "currency": "USD",
        "pricing_version": pricing_version(),
        "by_feature": [breakdown(key, feature_groups[key]) for key in sorted(feature_groups)],
        "by_model": [breakdown(key, model_groups[key]) for key in sorted(model_groups)],
        "recent_records": records[:20],
    }


async def user_usage_record_count(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(select(func.count()).select_from(LLMUsageRecord).where(LLMUsageRecord.user_id == user_id))
    return int(result.scalar_one())
