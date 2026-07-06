from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import get_db
from app.models import PracticePlan, Question, Session, Tag, User, UserTagStat, WrongBook
from app.schemas import PracticePlanOut, PracticePlanTaskOut


router = APIRouter(prefix="/me/practice-plan", tags=["practice-plan"])


def _score_value(value: Decimal | float | int | None) -> float:
    return float(value or 0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task(
    task_id: str,
    task_type: str,
    title: str,
    reason: str,
    outcome: str,
    action_label: str,
    payload: dict[str, Any],
    entrypoint: str = "create_session",
) -> dict[str, Any]:
    return {
        "id": task_id,
        "type": task_type,
        "title": title,
        "reason": reason,
        "outcome": outcome,
        "action_label": action_label,
        "entrypoint": entrypoint,
        "payload": payload,
    }


def _plan_out(plan: PracticePlan) -> PracticePlanOut:
    return PracticePlanOut(
        id=plan.id,
        date=plan.plan_date,
        recommended_tasks=[PracticePlanTaskOut(**item) for item in plan.recommended_tasks],
        weak_tags=plan.weak_tags,
        target_abilities=plan.target_abilities,
        generated_reason=plan.generated_reason,
        completed=plan.completed,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


async def _wrong_book_task(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(WrongBook, Question)
            .join(Question, Question.id == WrongBook.question_id)
            .where(WrongBook.user_id == user_id)
            .order_by(WrongBook.next_review.asc().nullslast(), WrongBook.fail_count.desc())
            .limit(1)
        )
    ).first()
    if not row:
        return None
    wrong, question = row
    return _task(
        "wrong-book-review",
        "wrong_book_review",
        "错题复习",
        f"这道题上次 {wrong.last_score or 0} 分，累计失误 {wrong.fail_count} 次。",
        "优先修复已经暴露的知识缺口。",
        "重练错题",
        {"mode": "single", "question_id": question.id},
    )


async def _weak_tags(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(UserTagStat, Tag)
            .join(Tag, Tag.id == UserTagStat.tag_id)
            .where(UserTagStat.user_id == user_id)
            .order_by(UserTagStat.avg_score.asc(), UserTagStat.attempts.desc())
            .limit(3)
        )
    ).all()
    return [
        {
            "tag_id": tag.id,
            "tag": tag.name,
            "category": tag.category,
            "avg_score": _score_value(stat.avg_score),
            "attempts": stat.attempts,
        }
        for stat, tag in rows
    ]


def _weak_tag_task(weak_tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not weak_tags:
        return None
    tag = weak_tags[0]
    return _task(
        "weak-tag-training",
        "weak_tag_training",
        "薄弱标签专项",
        f"{tag['tag']} 当前平均 {tag['avg_score']:.0f} 分，是近期优先补强项。",
        "通过单题训练更新该标签的能力画像。",
        "开始专项",
        {"mode": "single", "tag_ids": [tag["tag_id"]]},
    )


def _resume_session_task(session: Session) -> dict[str, Any]:
    mode = "模拟面试" if session.mode == "mock" else "单题训练"
    progress = f"第 {session.current_question_index}/{session.total_questions} 题"
    return _task(
        f"resume-session-{session.id}",
        "resume_session",
        "继续未完成会话",
        f"你有一个{mode}还在进行中，当前进度 {progress}。",
        "先完成已经开始的训练，避免能力数据断裂。",
        "继续训练",
        {"session_id": session.id, "href": f"/session/{session.id}"},
        entrypoint="open_page",
    )


async def _latest_active_session(db: AsyncSession, user_id: int, now: datetime | None = None) -> Session | None:
    current = now or _now()
    return (
        await db.execute(
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.status.in_(["created", "ongoing", "paused"]),
                or_(Session.deadline_at.is_(None), Session.deadline_at > current),
            )
            .order_by(Session.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _with_resume_task(tasks: list[dict[str, Any]], resume_task: dict[str, Any] | None) -> list[dict[str, Any]]:
    without_resume = [item for item in tasks if item.get("type") != "resume_session"]
    if not resume_task:
        return without_resume
    return [resume_task, *without_resume]


def _default_tasks(current_user: User) -> list[dict[str, Any]]:
    return [
        _task(
            "mock-interview",
            "mock_interview",
            "完整模拟面试",
            "用 45 分钟连续 Session 检验多题作答、追问抗压和节奏管理。",
            "生成报告，并继续沉淀错题与能力画像。",
            "开始模拟",
            {
                "mode": "mock",
                "company_id": current_user.target_company_id,
                "position_id": current_user.target_position_id,
            },
        ),
        _task(
            "single-question",
            "single_question",
            "单题快练",
            "当错题和能力画像还不充分时，先用一题真实 Session 建立训练数据。",
            "让下一次推荐有新的评分和标签依据。",
            "开始单题",
            {
                "mode": "single",
                "company_id": current_user.target_company_id,
                "position_id": current_user.target_position_id,
            },
        ),
    ]


def _compose_tasks(
    current_user: User,
    wrong_task: dict[str, Any] | None,
    weak_task: dict[str, Any] | None,
    resume_task: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tasks = []
    if wrong_task:
        tasks.append(wrong_task)
    if weak_task:
        tasks.append(weak_task)
    tasks.extend(_default_tasks(current_user))
    return _with_resume_task(tasks, resume_task)


def _generated_reason(wrong_task: dict[str, Any] | None, weak_task: dict[str, Any] | None, recent_reason: str | None) -> str:
    reason_parts = ["基于错题、薄弱标签和最近训练记录生成今日任务。"]
    if recent_reason:
        reason_parts.append(recent_reason)
    if not wrong_task and not weak_task:
        reason_parts.append("当前历史数据不足，优先通过单题和模拟面试建立训练画像。")
    return " ".join(reason_parts)


async def _recent_report_reason(db: AsyncSession, user_id: int) -> str | None:
    session = (
        await db.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.status == "finished")
            .order_by(Session.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not session:
        return None
    score = int((session.report or {}).get("overall_score", 0))
    mode = "模拟面试" if session.mode == "mock" else "单题训练"
    return f"最近一次{mode}得分 {score}，建议继续补齐短板。"


async def _build_plan(db: AsyncSession, current_user: User, plan_date: date) -> PracticePlan:
    weak_tags = await _weak_tags(db, current_user.id)

    resume_session = await _latest_active_session(db, current_user.id)
    resume_task = _resume_session_task(resume_session) if resume_session else None
    wrong_task = await _wrong_book_task(db, current_user.id)
    weak_task = _weak_tag_task(weak_tags)
    tasks = _compose_tasks(current_user, wrong_task, weak_task, resume_task)

    recent_reason = await _recent_report_reason(db, current_user.id)

    plan = PracticePlan(
        user_id=current_user.id,
        plan_date=plan_date,
        recommended_tasks=tasks,
        weak_tags=weak_tags,
        target_abilities=[item["tag"] for item in weak_tags] or ["结构化表达", "基础知识覆盖", "追问抗压"],
        generated_reason=_generated_reason(wrong_task, weak_task, recent_reason),
        completed=False,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def _sync_resume_task(db: AsyncSession, plan: PracticePlan, current_user: User) -> PracticePlan:
    resume_session = await _latest_active_session(db, current_user.id)
    resume_task = _resume_session_task(resume_session) if resume_session else None
    next_tasks = _with_resume_task(plan.recommended_tasks, resume_task)
    if next_tasks != plan.recommended_tasks:
        plan.recommended_tasks = next_tasks
        await db.commit()
        await db.refresh(plan)
    return plan


@router.get("/today", response_model=PracticePlanOut)
async def today_practice_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PracticePlanOut:
    today = date.today()
    plan = (
        await db.execute(select(PracticePlan).where(PracticePlan.user_id == current_user.id, PracticePlan.plan_date == today))
    ).scalar_one_or_none()
    if not plan:
        plan = await _build_plan(db, current_user, today)
    else:
        plan = await _sync_resume_task(db, plan, current_user)
    return _plan_out(plan)


@router.post("/{plan_id}/complete", response_model=PracticePlanOut)
async def complete_practice_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PracticePlanOut:
    plan = (
        await db.execute(select(PracticePlan).where(PracticePlan.id == plan_id, PracticePlan.user_id == current_user.id))
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Practice plan not found")
    plan.completed = True
    await db.commit()
    await db.refresh(plan)
    return _plan_out(plan)
