from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.llm import ChatMessage, DeepSeekLLM, LLMClient, LLMConfigurationError, LLMResponseError
from app.llm_gateway import GatewayLLMClient
from app.settings import get_settings


Action = Literal["followup_deeper", "followup_detail", "followup_hint", "verdict"]
Mastery = Literal["pass", "weak", "fail"]


@dataclass(frozen=True)
class InterviewQuestion:
    title: str
    answer_key: str
    company: str = "目标公司"
    position: str = "目标岗位"


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    msg_type: str


@dataclass
class Verdict:
    score: int
    mastery: Mastery
    feedback: str
    ideal_answer: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "mastery": self.mastery,
            "feedback": self.feedback,
            "ideal_answer": self.ideal_answer,
        }


@dataclass
class EvaluationResult:
    coverage: float
    correct_points: list[str] = field(default_factory=list)
    missing_points: list[str] = field(default_factory=list)
    wrong_points: list[str] = field(default_factory=list)
    action: Action = "verdict"
    followup: str = ""
    verdict: Verdict | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage,
            "correct_points": self.correct_points,
            "missing_points": self.missing_points,
            "wrong_points": self.wrong_points,
            "action": self.action,
            "followup": self.followup,
            "verdict": self.verdict.as_dict() if self.verdict else None,
        }


SKIP_WORDS = ("不会", "跳过", "不知道", "不清楚", "pass")
PROMPT_INJECTION_MARKERS = ("忽略", "ignore", "system prompt", "提示词", "answer_key", "标准答案")


def classify_candidate_input(answer: str) -> str:
    normalized = answer.strip().lower()
    if not normalized:
        return "is_offtopic"
    if any(word in normalized for word in PROMPT_INJECTION_MARKERS):
        return "is_prompt_injection"
    if any(word in normalized for word in SKIP_WORDS):
        return "is_answer"
    if len(normalized) < 16 and ("?" in normalized or "？" in normalized):
        return "is_question"
    return "is_answer"


def build_evaluation_prompt(
    question: InterviewQuestion,
    history: list[ConversationMessage],
    answer: str,
    depth: int,
) -> str:
    history_text = "\n".join(f"{m.role}/{m.msg_type}: {m.content}" for m in history[-12:])
    return f"""你是{question.company}的{question.position}资深面试官。当前题目:{question.title}
参考答案要点:{question.answer_key}
对话历史:{history_text}
候选人最新回答:{answer}
当前追问深度:{depth}/3

只输出 JSON:
{{
  "coverage": 0.0-1.0,
  "correct_points": ["..."],
  "missing_points": ["..."],
  "wrong_points": ["..."],
  "action": "followup_deeper | followup_detail | followup_hint | verdict",
  "followup": "下一句追问原话(action为verdict时为空)",
  "verdict": {{ "score": 0-100, "mastery": "pass|weak|fail",
               "feedback": "150字内点评", "ideal_answer": "完整参考答案" }}
}}"""


def _clamp_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score))


def _mastery_from_score(score: int) -> Mastery:
    if score >= 80:
        return "pass"
    if score >= 60:
        return "weak"
    return "fail"


def _fallback_verdict(question: InterviewQuestion, coverage: float, feedback: str) -> EvaluationResult:
    score = _clamp_score(coverage * 100)
    verdict = Verdict(
        score=score,
        mastery=_mastery_from_score(score),
        feedback=feedback,
        ideal_answer=question.answer_key,
    )
    return EvaluationResult(coverage=coverage, action="verdict", verdict=verdict)


def _normalize_result(raw: dict[str, Any], question: InterviewQuestion) -> EvaluationResult:
    coverage = max(0.0, min(1.0, float(raw.get("coverage") or 0.0)))
    verdict_raw = raw.get("verdict") or {}
    verdict: Verdict | None = None
    if isinstance(verdict_raw, dict) and verdict_raw:
        score = _clamp_score(verdict_raw.get("score"))
        verdict = Verdict(
            score=score,
            mastery=verdict_raw.get("mastery") if verdict_raw.get("mastery") in {"pass", "weak", "fail"} else _mastery_from_score(score),
            feedback=str(verdict_raw.get("feedback") or "本题已完成评估。")[:300],
            ideal_answer=str(verdict_raw.get("ideal_answer") or question.answer_key),
        )

    action = raw.get("action")
    if action not in {"followup_deeper", "followup_detail", "followup_hint", "verdict"}:
        action = "verdict" if verdict else "followup_detail"
    if action == "verdict" and not verdict:
        return _fallback_verdict(question, coverage, "回答已到当前轮次上限，建议对照参考答案补齐遗漏要点。")

    return EvaluationResult(
        coverage=coverage,
        correct_points=list(raw.get("correct_points") or []),
        missing_points=list(raw.get("missing_points") or []),
        wrong_points=list(raw.get("wrong_points") or []),
        action=action,
        followup=str(raw.get("followup") or ""),
        verdict=verdict,
    )


class InterviewerEngine:
    def __init__(self, llm: LLMClient | None = None) -> None:
        settings = get_settings()
        self.llm = llm or (GatewayLLMClient("interview_scoring") if settings.llm_gateway_enabled else DeepSeekLLM())
        self.last_llm_call_attempted = False
        self.last_llm_call_failed = False
        self.last_llm_error_type: str | None = None
        self.last_llm_attempts: list[Any] = []

    async def evaluate_answer(
        self,
        question: InterviewQuestion,
        history: list[ConversationMessage],
        answer: str,
        depth: int,
    ) -> EvaluationResult:
        self.last_llm_call_attempted = False
        self.last_llm_call_failed = False
        self.last_llm_error_type = None
        self.last_llm_attempts = []
        candidate_type = classify_candidate_input(answer)
        if any(word in answer.strip().lower() for word in SKIP_WORDS):
            return _fallback_verdict(question, 0.0, "候选人选择跳过。本题建议先掌握基础概念，再练习完整表达。")
        if candidate_type == "is_prompt_injection":
            return EvaluationResult(
                coverage=0.0,
                action="followup_hint",
                followup="我们回到题目本身。请直接说明你的解题思路、关键依据和可能的边界情况。",
            )
        if candidate_type in {"is_question", "is_offtopic"}:
            return EvaluationResult(
                coverage=0.0,
                action="followup_hint",
                followup="面试中需要先给出你的判断。你可以先讲核心概念，再补充一个具体例子。",
            )

        prompt = build_evaluation_prompt(question, history, answer, depth)
        try:
            self.last_llm_call_attempted = True
            raw = await self.llm.json_chat([ChatMessage(role="system", content=prompt)])
            self.last_llm_attempts = list(getattr(self.llm, "last_attempts", []))
            result = _normalize_result(raw, question)
        except (LLMConfigurationError, LLMResponseError) as exc:
            self.last_llm_attempts = list(getattr(self.llm, "last_attempts", []))
            self.last_llm_call_failed = True
            self.last_llm_error_type = exc.__class__.__name__
            result = self._local_fallback(question, answer, depth)

        return self._apply_transition_rules(question, result, depth)

    def _apply_transition_rules(self, question: InterviewQuestion, result: EvaluationResult, depth: int) -> EvaluationResult:
        if depth >= 3:
            if result.verdict:
                result.action = "verdict"
                result.followup = ""
                return result
            return _fallback_verdict(question, result.coverage, "追问已到上限。整体回答仍需补充关键细节和场景化取舍。")

        if result.action == "verdict":
            return result

        if result.coverage < 0.4 and depth == 0:
            result.action = "followup_hint"
            if not result.followup:
                result.followup = "先不用给完整答案。你可以从定义、典型场景和常见问题三个角度展开。"
        elif 0.4 <= result.coverage < 0.8:
            result.action = "followup_detail"
            if not result.followup:
                result.followup = "你讲到了方向。请补充关键步骤、边界条件和为什么这样取舍。"
        elif result.coverage >= 0.8 and depth < 2:
            result.action = "followup_deeper"
            if not result.followup:
                result.followup = "如果流量或数据规模扩大 10 倍，你的方案需要怎么调整？"
        return result

    def _local_fallback(self, question: InterviewQuestion, answer: str, depth: int) -> EvaluationResult:
        answer_norm = answer.lower()
        keywords = [token.strip().lower() for token in question.answer_key.replace("，", ",").replace("。", ",").split(",") if token.strip()]
        hit_count = sum(1 for token in keywords[:12] if token and token[:8] in answer_norm)
        coverage = min(0.9, max(0.15, len(answer) / 260 + hit_count * 0.08))
        if depth >= 2 or coverage >= 0.82:
            return _fallback_verdict(question, coverage, "回答有一定覆盖度，继续加强关键点完整性、场景化细节和方案取舍。")
        if coverage < 0.4 and depth == 0:
            return EvaluationResult(
                coverage=coverage,
                action="followup_hint",
                missing_points=["核心要点覆盖不足"],
                followup="先从定义和使用场景说起，再补充这个方案最容易出问题的地方。",
            )
        return EvaluationResult(
            coverage=coverage,
            action="followup_detail",
            missing_points=["需要补充细节和边界条件"],
            followup="你这个回答还比较概括。请讲一个具体例子，并说明关键步骤和取舍理由。",
        )

