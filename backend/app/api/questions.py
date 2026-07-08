from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Company, Position, Question, QuestionTag, Tag
from app.question_bank import PUBLISHED_QUESTION_STATUSES
from app.schemas import MetadataOut, QuestionListOut, QuestionOut, TagOut


router = APIRouter(prefix="/questions", tags=["questions"])


def _question_out(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        title=question.title,
        body=question.body,
        difficulty=question.difficulty,
        qtype=question.qtype,
        source_type=question.source_type,
        source_note=question.source_note,
        company=question.company,
        position=question.position,
        tags=[TagOut.model_validate(link.tag) for link in question.tag_links],
    )


def _apply_filters(
    stmt: Select[tuple[Question]],
    *,
    company_id: int | None,
    position_id: int | None,
    tag_ids: list[int],
    difficulty: int | None,
) -> Select[tuple[Question]]:
    stmt = stmt.where(Question.status.in_(PUBLISHED_QUESTION_STATUSES))
    if company_id:
        stmt = stmt.where(Question.company_id == company_id)
    if position_id:
        stmt = stmt.where(Question.position_id == position_id)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if tag_ids:
        stmt = stmt.join(QuestionTag).where(QuestionTag.tag_id.in_(tag_ids)).distinct()
    return stmt


@router.get("/meta", response_model=MetadataOut)
async def metadata(db: AsyncSession = Depends(get_db)) -> MetadataOut:
    companies = (await db.execute(select(Company).order_by(Company.tier, Company.name))).scalars().all()
    positions = (await db.execute(select(Position).order_by(Position.id))).scalars().all()
    tags = (await db.execute(select(Tag).order_by(Tag.category, Tag.name))).scalars().all()
    return MetadataOut(companies=companies, positions=positions, tags=tags)


@router.get("", response_model=QuestionListOut)
async def list_questions(
    company_id: int | None = None,
    position_id: int | None = None,
    tag_ids: list[int] = Query(default_factory=list),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> QuestionListOut:
    base = _apply_filters(
        select(Question),
        company_id=company_id,
        position_id=position_id,
        tag_ids=tag_ids,
        difficulty=difficulty,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.execute(
        base.options(
            selectinload(Question.company),
            selectinload(Question.position),
            selectinload(Question.tag_links).selectinload(QuestionTag.tag),
        )
        .order_by(Question.difficulty, Question.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return QuestionListOut(items=[_question_out(item) for item in rows.scalars().all()], total=total or 0)


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)) -> QuestionOut:
    question = await db.get(
        Question,
        question_id,
        options=[
            selectinload(Question.company),
            selectinload(Question.position),
            selectinload(Question.tag_links).selectinload(QuestionTag.tag),
        ],
    )
    if not question or question.status not in PUBLISHED_QUESTION_STATUSES:
        raise HTTPException(status_code=404, detail="Question not found")
    return _question_out(question)
