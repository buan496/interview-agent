from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db import get_db
from app.models import Question, QuestionTag, Session, Tag, User, UserTagStat, WrongBook
from app.schemas import RadarItemOut, ReportListItemOut, TagOut, WrongBookOut


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
