from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Literal
from uuid import uuid4

from app.core.interviewer import InterviewerEngine, InterviewQuestion
from app.llm_gateway import GatewayLLMClient, LLMGateway
from app.llm_usage import calculate_estimated_cost, estimate_completion_tokens, estimate_prompt_tokens
from app.settings import Settings


EvalDecision = Literal["better", "worse", "neutral"]


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    question: str
    candidate_answer_sanitized: str
    tags: list[str]
    difficulty: str
    rubric_version_ref: str
    expected_score_min: int
    expected_score_max: int
    expected_strength_tags: list[str] = field(default_factory=list)
    expected_weakness_tags: list[str] = field(default_factory=list)
    notes: str = ""
    reference_answer_sanitized: str = ""


@dataclass(frozen=True)
class EvalDataset:
    path: str
    cases: list[EvalCase]


@dataclass(frozen=True)
class EvalModelConfig:
    provider: str = "mock"
    model: str = "local-eval"
    feature: str = "interview_scoring"
    fallback_provider: str = "mock"
    fallback_model: str = "local-fallback"
    fallback_enabled: bool = True
    use_real_provider: bool = False


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    passed: bool
    score: int
    expected_score_min: int
    expected_score_max: int
    mastery: str
    action: str
    provider: str
    model: str
    fallback_used: bool
    latency_ms: int
    prompt_tokens_estimated: int
    completion_tokens_estimated: int
    estimated_cost: str
    error: str | None = None


@dataclass(frozen=True)
class EvalRunResult:
    eval_run_id: str
    dataset: str
    feature: str
    provider: str
    model: str
    total_cases: int
    pass_count: int
    fail_count: int
    score_within_range_rate: float
    average_latency_ms: float
    estimated_cost: str
    fallback_count: int
    errors: list[str]
    generated_at: str
    cases: list[EvalCaseResult]


@dataclass(frozen=True)
class EvalComparison:
    baseline_run_id: str
    candidate_run_id: str
    decision: EvalDecision
    regression_detected: bool
    pass_rate_delta: float
    average_latency_delta_ms: float
    estimated_cost_delta: str
    failure_count_delta: int
    fallback_count_delta: int
    recommended_decision: str


SENSITIVE_MARKERS = (
    "authorization",
    "bearer ",
    "token",
    "secret",
    "api_key",
    "apikey",
    "password",
    "000000",
    "sk-",
    "gho_",
)


def load_eval_dataset(path: str | Path) -> EvalDataset:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {dataset_path}")
    cases: list[EvalCase] = []
    for line_number, raw_line in enumerate(dataset_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {dataset_path}:{line_number}: {exc}") from exc
        case = EvalCase(
            case_id=str(payload["case_id"]),
            question=str(payload["question"]),
            candidate_answer_sanitized=str(payload["candidate_answer_sanitized"]),
            tags=list(payload.get("tags") or []),
            difficulty=str(payload.get("difficulty") or "medium"),
            rubric_version_ref=str(payload.get("rubric_version_ref") or "system_default:v1"),
            expected_score_min=int(payload["expected_score_min"]),
            expected_score_max=int(payload["expected_score_max"]),
            expected_strength_tags=list(payload.get("expected_strength_tags") or []),
            expected_weakness_tags=list(payload.get("expected_weakness_tags") or []),
            notes=str(payload.get("notes") or ""),
            reference_answer_sanitized=str(payload.get("reference_answer_sanitized") or ""),
        )
        validate_eval_case(case, dataset_path, line_number)
        cases.append(case)
    if not cases:
        raise ValueError(f"Eval dataset has no cases: {dataset_path}")
    return EvalDataset(path=str(dataset_path), cases=cases)


def validate_eval_case(case: EvalCase, dataset_path: Path | None = None, line_number: int | None = None) -> None:
    context = f" at {dataset_path}:{line_number}" if dataset_path and line_number else ""
    if not case.case_id:
        raise ValueError(f"Eval case missing case_id{context}")
    if case.expected_score_min < 0 or case.expected_score_max > 100 or case.expected_score_min > case.expected_score_max:
        raise ValueError(f"Invalid expected score range for {case.case_id}{context}")
    text = " ".join([
        case.question,
        case.candidate_answer_sanitized,
        case.notes,
        case.reference_answer_sanitized,
    ]).lower()
    if any(marker in text for marker in SENSITIVE_MARKERS):
        raise ValueError(f"Eval case may contain sensitive marker: {case.case_id}{context}")


async def run_eval_case(case: EvalCase, config: EvalModelConfig) -> EvalCaseResult:
    settings = build_eval_settings(config)
    gateway = LLMGateway(settings=settings)
    engine = InterviewerEngine(GatewayLLMClient(config.feature, gateway))
    question = InterviewQuestion(
        title=case.question,
        answer_key=case.reference_answer_sanitized or case.notes or ", ".join(case.tags),
        company="Eval Company",
        position="Agent Engineer",
    )
    result = await engine.evaluate_answer(question, history=[], answer=case.candidate_answer_sanitized, depth=2)
    score = result.verdict.score if result.verdict else int(round(result.coverage * 100))
    attempts = list(engine.last_llm_attempts)
    success_attempt = next((attempt for attempt in reversed(attempts) if attempt.status == "success"), None)
    provider = success_attempt.provider if success_attempt else config.provider
    model = success_attempt.model if success_attempt else config.model
    fallback_used = bool(success_attempt.fallback) if success_attempt else False
    latency_ms = sum(max(attempt.latency_ms, 0) for attempt in attempts)
    prompt_tokens = estimate_prompt_tokens(question, [], case.candidate_answer_sanitized, 2)
    completion_tokens = estimate_completion_tokens(result)
    estimated_cost = calculate_estimated_cost(provider, model, prompt_tokens, completion_tokens)
    return EvalCaseResult(
        case_id=case.case_id,
        passed=case.expected_score_min <= score <= case.expected_score_max,
        score=score,
        expected_score_min=case.expected_score_min,
        expected_score_max=case.expected_score_max,
        mastery=result.verdict.mastery if result.verdict else "unknown",
        action=result.action,
        provider=provider,
        model=model,
        fallback_used=fallback_used,
        latency_ms=latency_ms,
        prompt_tokens_estimated=prompt_tokens,
        completion_tokens_estimated=completion_tokens,
        estimated_cost=str(estimated_cost),
        error=None,
    )


async def run_eval_suite(dataset: EvalDataset, config: EvalModelConfig, eval_run_id: str | None = None) -> EvalRunResult:
    validate_eval_model_config(config)
    case_results: list[EvalCaseResult] = []
    errors: list[str] = []
    for case in dataset.cases:
        try:
            case_results.append(await run_eval_case(case, config))
        except Exception as exc:  # noqa: BLE001 - eval runner records per-case failures
            errors.append(f"{case.case_id}: {exc.__class__.__name__}")
            case_results.append(
                EvalCaseResult(
                    case_id=case.case_id,
                    passed=False,
                    score=0,
                    expected_score_min=case.expected_score_min,
                    expected_score_max=case.expected_score_max,
                    mastery="error",
                    action="error",
                    provider=config.provider,
                    model=config.model,
                    fallback_used=False,
                    latency_ms=0,
                    prompt_tokens_estimated=0,
                    completion_tokens_estimated=0,
                    estimated_cost="0.000000",
                    error=exc.__class__.__name__,
                )
            )
    return calculate_eval_summary(
        dataset=dataset,
        config=config,
        case_results=case_results,
        errors=errors,
        eval_run_id=eval_run_id,
    )


def calculate_eval_summary(
    *,
    dataset: EvalDataset,
    config: EvalModelConfig,
    case_results: list[EvalCaseResult],
    errors: list[str] | None = None,
    eval_run_id: str | None = None,
) -> EvalRunResult:
    pass_count = sum(1 for item in case_results if item.passed)
    total_cases = len(case_results)
    total_cost = sum((Decimal(item.estimated_cost) for item in case_results), Decimal("0.000000"))
    average_latency = mean([item.latency_ms for item in case_results]) if case_results else 0.0
    return EvalRunResult(
        eval_run_id=eval_run_id or f"eval-{uuid4().hex[:12]}",
        dataset=dataset.path,
        feature=config.feature,
        provider=config.provider,
        model=config.model,
        total_cases=total_cases,
        pass_count=pass_count,
        fail_count=total_cases - pass_count,
        score_within_range_rate=round(pass_count / total_cases, 4) if total_cases else 0.0,
        average_latency_ms=round(average_latency, 2),
        estimated_cost=str(total_cost.quantize(Decimal("0.000001"))),
        fallback_count=sum(1 for item in case_results if item.fallback_used),
        errors=list(errors or []),
        generated_at=datetime.now(timezone.utc).isoformat(),
        cases=case_results,
    )


def compare_model_results(baseline: EvalRunResult, candidate: EvalRunResult) -> EvalComparison:
    pass_rate_delta = candidate.score_within_range_rate - baseline.score_within_range_rate
    latency_delta = candidate.average_latency_ms - baseline.average_latency_ms
    cost_delta = Decimal(candidate.estimated_cost) - Decimal(baseline.estimated_cost)
    failure_delta = candidate.fail_count - baseline.fail_count
    fallback_delta = candidate.fallback_count - baseline.fallback_count
    regression = pass_rate_delta < -0.05 or failure_delta > 0
    if regression:
        decision: EvalDecision = "worse"
        recommendation = "NO-GO: candidate regresses pass rate or failure count."
    elif pass_rate_delta > 0.05 and cost_delta <= Decimal("0.000001"):
        decision = "better"
        recommendation = "GO: candidate improves quality without material cost increase."
    else:
        decision = "neutral"
        recommendation = "REVIEW: candidate is comparable; review latency, cost and qualitative output manually."
    return EvalComparison(
        baseline_run_id=baseline.eval_run_id,
        candidate_run_id=candidate.eval_run_id,
        decision=decision,
        regression_detected=regression,
        pass_rate_delta=round(pass_rate_delta, 4),
        average_latency_delta_ms=round(latency_delta, 2),
        estimated_cost_delta=str(cost_delta.quantize(Decimal("0.000001"))),
        failure_count_delta=failure_delta,
        fallback_count_delta=fallback_delta,
        recommended_decision=recommendation,
    )


def build_eval_settings(config: EvalModelConfig) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=config.provider,
        llm_default_provider=config.provider,
        llm_default_model=config.model,
        llm_route_interview_scoring=f"{config.provider}/{config.model}" if config.feature == "interview_scoring" else "",
        llm_fallback_provider=config.fallback_provider,
        llm_fallback_model=config.fallback_model,
        llm_fallback_enabled=config.fallback_enabled,
        llm_max_retries=1,
        llm_usage_metering_enabled=False,
    )


def validate_eval_model_config(config: EvalModelConfig) -> None:
    providers = [config.provider]
    if config.fallback_enabled:
        providers.append(config.fallback_provider)
    real_providers = [provider for provider in providers if provider.strip().lower() != "mock"]
    if not real_providers:
        return
    env_enabled = os.getenv("EVAL_ALLOW_REAL_PROVIDER", "").lower() in {"1", "true", "yes"}
    if not (config.use_real_provider and env_enabled):
        raise ValueError("Real provider eval requires use_real_provider=True and EVAL_ALLOW_REAL_PROVIDER=true")


def result_to_dict(result: EvalRunResult | EvalCaseResult | EvalComparison) -> dict[str, Any]:
    return asdict(result)


def write_eval_report(result: EvalRunResult, output_dir: str | Path) -> tuple[Path, Path]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / f"{result.eval_run_id}.json"
    md_path = target_dir / f"{result.eval_run_id}.md"
    json_path.write_text(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_summary(result), encoding="utf-8")
    return json_path, md_path


def render_markdown_summary(result: EvalRunResult) -> str:
    lines = [
        f"# Evaluation Summary: {result.eval_run_id}",
        "",
        f"- dataset: `{result.dataset}`",
        f"- feature: `{result.feature}`",
        f"- route: `{result.provider}/{result.model}`",
        f"- total cases: {result.total_cases}",
        f"- pass count: {result.pass_count}",
        f"- fail count: {result.fail_count}",
        f"- score within range rate: {result.score_within_range_rate}",
        f"- average latency ms: {result.average_latency_ms}",
        f"- estimated cost: {result.estimated_cost} USD",
        f"- fallback count: {result.fallback_count}",
        "",
        "| case_id | passed | score | expected | provider/model | fallback | latency_ms |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result.cases:
        lines.append(
            f"| {item.case_id} | {item.passed} | {item.score} | "
            f"{item.expected_score_min}-{item.expected_score_max} | "
            f"{item.provider}/{item.model} | {item.fallback_used} | {item.latency_ms} |"
        )
    if result.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in result.errors)
    return "\n".join(lines) + "\n"


def load_eval_run_result(path: str | Path) -> EvalRunResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [EvalCaseResult(**item) for item in payload.get("cases", [])]
    payload["cases"] = cases
    return EvalRunResult(**payload)


def run_eval_suite_sync(dataset: EvalDataset, config: EvalModelConfig, eval_run_id: str | None = None) -> EvalRunResult:
    return asyncio.run(run_eval_suite(dataset, config, eval_run_id=eval_run_id))
