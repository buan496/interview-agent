from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db import get_db
from app.models import EvaluationResult, Question, QuestionTag, Session, Tag, User, UserTagStat, WrongBook
from app.schemas import AbilityProfileOut, AbilityTagProfileOut, RadarItemOut, ReportListItemOut, TagOut, WrongBookOut


router = APIRouter(prefix="/me", tags=["stats"])


@router.get("/wrong-book", response_model=list[WrongBookOut])
async def wrong_book(
    due: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WrongBookOut]:
    stmt = (
        select(WrongBook, Question)
        .join(Question, Question.id == WrongBook.question_id)
        .where(WrongBook.user_id == current_user.id)
        .options(selectinload(Question.tag_links).selectinload(QuestionTag.tag))
        .order_by(WrongBook.next_review.asc().nullslast())
    )
    if due == "today":
        stmt = stmt.where(WrongBook.next_review <= date.today())
    rows = (await db.execute(stmt)).all()
    return [
        WrongBookOut(
            question_id=question.id,
            title=question.title,
            last_score=wrong.last_score,
            fail_count=wrong.fail_count,
            next_review=wrong.next_review,
            tags=[TagOut.model_validate(link.tag) for link in question.tag_links],
        )
        for wrong, question in rows
    ]


@router.get("/radar", response_model=list[RadarItemOut])
async def radar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RadarItemOut]:
    rows = (
        await db.execute(
            select(UserTagStat, Tag)
            .join(Tag, Tag.id == UserTagStat.tag_id)
            .where(UserTagStat.user_id == current_user.id)
            .order_by(Tag.category, Tag.name)
        )
    ).all()
    return [RadarItemOut(tag=tag.name, avg_score=stat.avg_score, attempts=stat.attempts) for stat, tag in rows]


def _mastery_level(score: Decimal) -> str:
    if score >= Decimal("85"):
        return "strong"
    if score >= Decimal("70"):
        return "stable"
    return "weak"


@router.get("/ability-profile", response_model=AbilityProfileOut)
async def ability_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AbilityProfileOut:
    session_rows = (
        await db.execute(
            select(Session)
            .where(Session.user_id == current_user.id)
            .order_by(Session.started_at.desc(), Session.id.desc())
        )
    ).scalars().all()

    completed_sessions = [item for item in session_rows if item.status == "finished"]
    scores: list[int] = []
    for item in completed_sessions:
        score_value = (item.report or {}).get("overall_score")
        if score_value is not None:
            scores.append(int(score_value))

    total_questions = sum(item.total_questions or 0 for item in session_rows)
    overall_score = round(sum(scores) / len(scores)) if scores else None

    wrong_rows = (
        await db.execute(
            select(QuestionTag.tag_id, func.coalesce(func.sum(WrongBook.fail_count), 0))
            .join(WrongBook, WrongBook.question_id == QuestionTag.question_id)
            .where(WrongBook.user_id == current_user.id)
            .group_by(QuestionTag.tag_id)
        )
    ).all()
    wrong_counts = {tag_id: int(fail_count or 0) for tag_id, fail_count in wrong_rows}

    last_practiced_rows = (
        await db.execute(
            select(QuestionTag.tag_id, func.max(EvaluationResult.created_at))
            .join(EvaluationResult, EvaluationResult.question_id == QuestionTag.question_id)
            .where(EvaluationResult.user_id == current_user.id)
            .group_by(QuestionTag.tag_id)
        )
    ).all()
    last_practiced = {tag_id: practiced_at for tag_id, practiced_at in last_practiced_rows}

    stat_rows = (
        await db.execute(
            select(UserTagStat, Tag)
            .join(Tag, Tag.id == UserTagStat.tag_id)
            .where(UserTagStat.user_id == current_user.id)
            .order_by(Tag.category, Tag.name)
        )
    ).all()
    tag_profiles = [
        AbilityTagProfileOut(
            tag_id=tag.id,
            tag=tag.name,
            category=tag.category,
            average_score=stat.avg_score,
            practice_count=stat.attempts,
            wrong_count=wrong_counts.get(tag.id, 0),
            mastery_level=_mastery_level(stat.avg_score),
            last_practiced_at=last_practiced.get(tag.id),
        )
        for stat, tag in stat_rows
    ]

    strengths = sorted(
        [item for item in tag_profiles if item.mastery_level == "strong" and item.practice_count > 0],
        key=lambda item: (-item.average_score, -item.practice_count, item.tag),
    )[:5]
    weaknesses = sorted(
        [item for item in tag_profiles if item.mastery_level == "weak" or item.wrong_count > 0],
        key=lambda item: (item.mastery_level != "weak", -item.wrong_count, item.average_score, item.tag),
    )[:5]

    updated_candidates: list[datetime] = [
        timestamp
        for item in session_rows
        for timestamp in (item.updated_at, item.ended_at, item.finished_at, item.started_at)
        if timestamp is not None
    ]
    updated_candidates.extend(item.last_practiced_at for item in tag_profiles if item.last_practiced_at is not None)

    return AbilityProfileOut(
        overall_score=overall_score,
        total_sessions=len(session_rows),
        completed_sessions=len(completed_sessions),
        total_questions=total_questions,
        updated_at=max(updated_candidates) if updated_candidates else None,
        strengths=strengths,
        weaknesses=weaknesses,
        tag_profiles=tag_profiles,
    )


@router.get("/reports", response_model=list[ReportListItemOut])
async def reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReportListItemOut]:
    rows = (
        await db.execute(
            select(Session)
            .where(Session.user_id == current_user.id, Session.status == "finished")
            .order_by(Session.started_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [
        ReportListItemOut(
            session_id=item.id,
            mode=item.mode,
            status=item.status,
            overall_score=int((item.report or {}).get("overall_score", 0)),
            started_at=item.started_at,
            ended_at=item.ended_at,
        )
        for item in rows
    ]
