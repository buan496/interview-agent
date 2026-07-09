from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentMemory,
    AsyncJob,
    EvaluationResult,
    LLMUsageRecord,
    Message,
    PracticePlan,
    Session,
    SessionQuestion,
    User,
    UserTagStat,
    WrongBook,
)
from app.observability import mask_phone


CONFIRMATION_PHRASE = "DELETE_MY_DATA"

SENSITIVE_EXPORT_KEYS = {
    "answer",
    "answer_key",
    "answer_reference",
    "answer_text",
    "api_key",
    "authorization",
    "code",
    "completion",
    "completion_text",
    "content",
    "jwt",
    "password",
    "phone",
    "prompt",
    "prompt_template",
    "prompt_text",
    "raw_model_output",
    "secret",
    "token",
    "verification_code",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def sanitize_export_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            is_sensitive = (
                normalized_key in SENSITIVE_EXPORT_KEYS
                or normalized_key.endswith("_secret")
                or normalized_key.endswith("_token")
                or "password" in normalized_key
                or "api_key" in normalized_key
            )
            if is_sensitive:
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = sanitize_export_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_export_payload(item) for item in value[:100]]
    if isinstance(value, tuple):
        return [sanitize_export_payload(item) for item in value[:100]]
    return _json_value(value)


async def get_user_data_summary(db: AsyncSession, user_id: int) -> dict[str, Any]:
    session_ids = (await db.execute(select(Session.id).where(Session.user_id == user_id))).scalars().all()
    sq_ids: list[int] = []
    if session_ids:
        sq_ids = (await db.execute(select(SessionQuestion.id).where(SessionQuestion.session_id.in_(session_ids)))).scalars().all()

    return {
        "scope": "current_user",
        "counts": {
            "sessions": int(await db.scalar(select(func.count()).select_from(Session).where(Session.user_id == user_id)) or 0),
            "session_questions": len(sq_ids),
            "messages": int(await db.scalar(select(func.count()).select_from(Message).where(Message.sq_id.in_(sq_ids))) or 0) if sq_ids else 0,
            "evaluation_results": int(await db.scalar(select(func.count()).select_from(EvaluationResult).where(EvaluationResult.user_id == user_id)) or 0),
            "reports": int(
                await db.scalar(select(func.count()).select_from(Session).where(Session.user_id == user_id, Session.report.is_not(None))) or 0
            ),
            "wrong_book": int(await db.scalar(select(func.count()).select_from(WrongBook).where(WrongBook.user_id == user_id)) or 0),
            "user_tag_stats": int(await db.scalar(select(func.count()).select_from(UserTagStat).where(UserTagStat.user_id == user_id)) or 0),
            "practice_plans": int(await db.scalar(select(func.count()).select_from(PracticePlan).where(PracticePlan.user_id == user_id)) or 0),
            "agent_memories": int(await db.scalar(select(func.count()).select_from(AgentMemory).where(AgentMemory.user_id == user_id)) or 0),
            "async_jobs": int(await db.scalar(select(func.count()).select_from(AsyncJob).where(AsyncJob.user_id == user_id)) or 0),
            "llm_usage_records": int(await db.scalar(select(func.count()).select_from(LLMUsageRecord).where(LLMUsageRecord.user_id == user_id)) or 0),
        },
    }


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "phone_masked": mask_phone(user.phone),
        "nickname": user.nickname,
        "level": user.level,
        "role": user.role,
        "target_company_id": user.target_company_id,
        "target_position_id": user.target_position_id,
        "created_at": _json_value(user.created_at),
    }


def _session_payload(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "mode": session.mode,
        "status": session.status,
        "started_at": _json_value(session.started_at),
        "finished_at": _json_value(session.finished_at),
        "ended_at": _json_value(session.ended_at),
        "total_questions": session.total_questions,
        "end_reason": session.end_reason,
        "overall_score": (session.report or {}).get("overall_score") if isinstance(session.report, dict) else None,
    }


def _session_question_payload(sq: SessionQuestion) -> dict[str, Any]:
    return {
        "id": sq.id,
        "session_id": sq.session_id,
        "question_id": sq.question_id,
        "order_no": sq.order_no,
        "status": sq.status,
        "submitted_at": _json_value(sq.submitted_at),
        "scored_at": _json_value(sq.scored_at),
        "final_score": sq.final_score,
        "mastery": sq.mastery,
        "followup_count": sq.followup_count,
        "answer_text": "<redacted>" if sq.answer_text else None,
    }


def _evaluation_payload(result: EvaluationResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "session_id": result.session_id,
        "sq_id": result.sq_id,
        "question_id": result.question_id,
        "score": result.score,
        "mastery": result.mastery,
        "verdict": result.verdict,
        "strengths": sanitize_export_payload(result.strengths or []),
        "missing_points": sanitize_export_payload(result.missing_points or []),
        "expression_issues": sanitize_export_payload(result.expression_issues or []),
        "followup_failures": sanitize_export_payload(result.followup_failures or []),
        "action_items": sanitize_export_payload(result.action_items or []),
        "model_name": result.model_name,
        "prompt_version": result.prompt_version,
        "rubric_version_id": result.rubric_version_id,
        "created_at": _json_value(result.created_at),
    }


def _report_payload(session: Session) -> dict[str, Any]:
    report = session.report if isinstance(session.report, dict) else {}
    questions = report.get("questions") if isinstance(report.get("questions"), list) else []
    return {
        "session_id": session.id,
        "mode": session.mode,
        "status": session.status,
        "overall_score": report.get("overall_score"),
        "summary": report.get("summary"),
        "ended_at": _json_value(session.ended_at),
        "questions": [
            sanitize_export_payload(
                {
                    "sq_id": item.get("sq_id"),
                    "question_id": item.get("question_id"),
                    "title": item.get("title"),
                    "score": item.get("score"),
                    "mastery": item.get("mastery"),
                    "feedback": item.get("feedback"),
                    "strengths": item.get("strengths"),
                    "missing_points": item.get("missing_points"),
                    "action_items": item.get("action_items"),
                    "rubric_version_id": item.get("rubric_version_id"),
                }
            )
            for item in questions
            if isinstance(item, dict)
        ],
    }


async def build_user_data_export(db: AsyncSession, user: User) -> dict[str, Any]:
    user_id = user.id
    sessions = (await db.execute(select(Session).where(Session.user_id == user_id).order_by(Session.started_at.desc()))).scalars().all()
    session_ids = [session.id for session in sessions]
    sqs = (
        (await db.execute(select(SessionQuestion).where(SessionQuestion.session_id.in_(session_ids)).order_by(SessionQuestion.id))).scalars().all()
        if session_ids
        else []
    )
    evaluations = (await db.execute(select(EvaluationResult).where(EvaluationResult.user_id == user_id).order_by(EvaluationResult.created_at.desc()))).scalars().all()
    wrong_book = (await db.execute(select(WrongBook).where(WrongBook.user_id == user_id))).scalars().all()
    tag_stats = (await db.execute(select(UserTagStat).where(UserTagStat.user_id == user_id))).scalars().all()
    plans = (await db.execute(select(PracticePlan).where(PracticePlan.user_id == user_id).order_by(PracticePlan.plan_date.desc()))).scalars().all()
    memories = (await db.execute(select(AgentMemory).where(AgentMemory.user_id == user_id).order_by(AgentMemory.updated_at.desc()))).scalars().all()
    jobs = (await db.execute(select(AsyncJob).where(AsyncJob.user_id == user_id).order_by(AsyncJob.created_at.desc()).limit(100))).scalars().all()
    usage = (await db.execute(select(LLMUsageRecord).where(LLMUsageRecord.user_id == user_id).order_by(LLMUsageRecord.created_at.desc()).limit(100))).scalars().all()

    export = {
        "export_version": "privacy-export-v1",
        "user": _user_payload(user),
        "summary": await get_user_data_summary(db, user_id),
        "sessions": [_session_payload(session) for session in sessions],
        "session_questions": [_session_question_payload(sq) for sq in sqs],
        "evaluation_results": [_evaluation_payload(item) for item in evaluations],
        "reports": [_report_payload(session) for session in sessions if isinstance(session.report, dict)],
        "wrong_book": [
            {"question_id": item.question_id, "last_score": item.last_score, "fail_count": item.fail_count, "next_review": _json_value(item.next_review)}
            for item in wrong_book
        ],
        "user_tag_stats": [
            {"tag_id": item.tag_id, "attempts": item.attempts, "avg_score": _json_value(item.avg_score)}
            for item in tag_stats
        ],
        "practice_plans": [
            {
                "id": item.id,
                "plan_date": _json_value(item.plan_date),
                "recommended_tasks": sanitize_export_payload(item.recommended_tasks or []),
                "weak_tags": sanitize_export_payload(item.weak_tags or []),
                "target_abilities": sanitize_export_payload(item.target_abilities or []),
                "completed": item.completed,
                "created_at": _json_value(item.created_at),
            }
            for item in plans
        ],
        "agent_memories": [
            {
                "id": item.id,
                "memory_type": item.memory_type,
                "title": item.title,
                "summary": item.summary,
                "tags_json": sanitize_export_payload(item.tags_json or []),
                "evidence_json": sanitize_export_payload(item.evidence_json or []),
                "confidence": _json_value(item.confidence),
                "status": item.status,
                "source_type": item.source_type,
                "created_at": _json_value(item.created_at),
                "updated_at": _json_value(item.updated_at),
            }
            for item in memories
        ],
        "async_jobs": [
            {
                "id": item.id,
                "job_type": item.job_type,
                "status": item.status,
                "payload_json": sanitize_export_payload(item.payload_json or {}),
                "result_json": sanitize_export_payload(item.result_json or {}),
                "error_type": item.error_type,
                "attempts": item.attempts,
                "max_attempts": item.max_attempts,
                "created_at": _json_value(item.created_at),
                "finished_at": _json_value(item.finished_at),
            }
            for item in jobs
        ],
        "llm_usage_records": [
            {
                "id": item.id,
                "session_id": item.session_id,
                "feature": item.feature,
                "provider": item.provider,
                "model": item.model,
                "prompt_tokens": item.prompt_tokens,
                "completion_tokens": item.completion_tokens,
                "total_tokens": item.total_tokens,
                "estimated_cost": _json_value(item.estimated_cost),
                "currency": item.currency,
                "pricing_version": item.pricing_version,
                "latency_ms": item.latency_ms,
                "status": item.status,
                "error_type": item.error_type,
                "created_at": _json_value(item.created_at),
            }
            for item in usage
        ],
    }
    return sanitize_export_payload(export)


async def delete_user_training_data(db: AsyncSession, user_id: int) -> dict[str, Any]:
    summary_before = await get_user_data_summary(db, user_id)
    session_ids = (await db.execute(select(Session.id).where(Session.user_id == user_id))).scalars().all()
    sq_ids: list[int] = []
    if session_ids:
        sq_ids = (await db.execute(select(SessionQuestion.id).where(SessionQuestion.session_id.in_(session_ids)))).scalars().all()

    if sq_ids:
        await db.execute(delete(Message).where(Message.sq_id.in_(sq_ids)))
    await db.execute(delete(EvaluationResult).where(EvaluationResult.user_id == user_id))
    if session_ids:
        await db.execute(delete(SessionQuestion).where(SessionQuestion.session_id.in_(session_ids)))
        await db.execute(delete(LLMUsageRecord).where(LLMUsageRecord.user_id == user_id))
        await db.execute(delete(Session).where(Session.user_id == user_id))
    else:
        await db.execute(delete(LLMUsageRecord).where(LLMUsageRecord.user_id == user_id))
    await db.execute(delete(WrongBook).where(WrongBook.user_id == user_id))
    await db.execute(delete(UserTagStat).where(UserTagStat.user_id == user_id))
    await db.execute(delete(PracticePlan).where(PracticePlan.user_id == user_id))
    await db.execute(delete(AgentMemory).where(AgentMemory.user_id == user_id))
    await db.execute(delete(AsyncJob).where(AsyncJob.user_id == user_id))
    await db.commit()
    return {"scope": "training_data", "deleted_counts": summary_before["counts"]}
