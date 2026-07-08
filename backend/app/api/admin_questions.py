from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_content_operator_or_admin
from app.audit import record_audit_event
from app.db import get_db
from app.models import Company, Position, Question, QuestionTag, Tag, User
from app.observability import log_event
from app.question_bank import QUESTION_BANK_STATUSES, QUESTION_STATUS_PUBLISHED
from app.schemas import (
    CompanyOut,
    PositionOut,
    QuestionBankCreateRequest,
    QuestionBankListOut,
    QuestionBankQuestionOut,
    QuestionBankUpdateRequest,
    TagOut,
)


router = APIRouter(prefix="/admin/questions", tags=["admin-questions"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _question_out(question: Question) -> QuestionBankQuestionOut:
    return QuestionBankQuestionOut(
        id=question.id,
        title=question.title,
        body=question.body,
        answer_reference=question.answer_key,
        difficulty=question.difficulty,
        qtype=question.qtype,
        source_type=question.source_type,
        source_note=question.source_note,
        status=question.status,
        company=CompanyOut.model_validate(question.company) if question.company else None,
        position=PositionOut.model_validate(question.position) if question.position else None,
        tags=[TagOut.model_validate(link.tag) for link in question.tag_links],
        created_by_user_id=question.created_by_user_id,
        updated_by_user_id=question.updated_by_user_id,
        created_at=question.created_at,
        updated_at=question.updated_at,
        published_at=question.published_at,
        archived_at=question.archived_at,
    )


def _eager_options():
    return (
        selectinload(Question.company),
        selectinload(Question.position),
        selectinload(Question.tag_links).selectinload(QuestionTag.tag),
    )


async def _load_question(db: AsyncSession, question_id: int) -> Question:
    question = (
        await db.execute(
            select(Question)
            .where(Question.id == question_id)
            .options(*_eager_options())
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


async def _resolve_company(db: AsyncSession, company_id: int | None, company_name: str | None) -> Company | None:
    if company_id is not None:
        item = await db.get(Company, company_id)
        if not item:
            raise HTTPException(status_code=404, detail="Company not found")
        return item
    if not company_name:
        return None
    item = (await db.execute(select(Company).where(Company.name == company_name))).scalar_one_or_none()
    if item:
        return item
    item = Company(name=company_name, region="CN", tier=2)
    db.add(item)
    await db.flush()
    return item


async def _resolve_position(db: AsyncSession, position_id: int | None, position_name: str | None) -> Position | None:
    if position_id is not None:
        item = await db.get(Position, position_id)
        if not item:
            raise HTTPException(status_code=404, detail="Position not found")
        return item
    if not position_name:
        return None
    item = (await db.execute(select(Position).where(Position.name == position_name))).scalar_one_or_none()
    if item:
        return item
    item = Position(name=position_name)
    db.add(item)
    await db.flush()
    return item


async def _resolve_tag(db: AsyncSession, name: str) -> Tag:
    item = (await db.execute(select(Tag).where(Tag.name == name))).scalar_one_or_none()
    if item:
        return item
    item = Tag(name=name, category="managed")
    db.add(item)
    await db.flush()
    return item


async def _replace_tags(db: AsyncSession, question: Question, tag_names: list[str]) -> None:
    normalized = []
    seen = set()
    for raw_name in tag_names:
        name = raw_name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name[:50])

    await db.execute(delete(QuestionTag).where(QuestionTag.question_id == question.id))
    await db.flush()
    for name in normalized:
        tag = await _resolve_tag(db, name)
        db.add(QuestionTag(question_id=question.id, tag_id=tag.id))


def _apply_admin_filters(
    stmt: Select[tuple[Question]],
    *,
    status: str | None,
    tag: str | None,
    difficulty: int | None,
    position_id: int | None,
    position: str | None,
) -> Select[tuple[Question]]:
    if status:
        stmt = stmt.where(Question.status == status)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if position_id:
        stmt = stmt.where(Question.position_id == position_id)
    if position:
        stmt = stmt.join(Position, Position.id == Question.position_id).where(Position.name == position)
    if tag:
        stmt = stmt.join(QuestionTag).join(Tag).where(Tag.name == tag).distinct()
    return stmt


async def _record_question_audit(
    db: AsyncSession,
    *,
    action: str,
    actor: User,
    question: Question,
    request: Request | None,
    changed_fields: list[str] | None = None,
) -> None:
    await record_audit_event(
        db,
        action=action,
        status="success",
        actor=actor,
        actor_role=actor.role,
        resource_type="question",
        resource_id=str(question.id),
        request=request,
        metadata={
            "question_id": question.id,
            "status": question.status,
            "difficulty": question.difficulty,
            "qtype": question.qtype,
            "tag_count": len(question.tag_links),
            "title_length": len(question.title),
            "prompt_length": len(question.body or ""),
            "answer_reference_length": len(question.answer_key),
            "changed_fields": changed_fields or [],
        },
    )


@router.get("", response_model=QuestionBankListOut)
async def list_managed_questions(
    status: str | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=50),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    position_id: int | None = Query(default=None, ge=1),
    position: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _operator: User = Depends(require_content_operator_or_admin),
) -> QuestionBankListOut:
    if status and status not in QUESTION_BANK_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported question status")
    base = _apply_admin_filters(
        select(Question),
        status=status,
        tag=tag,
        difficulty=difficulty,
        position_id=position_id,
        position=position,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.execute(
        base.options(*_eager_options()).order_by(Question.updated_at.desc(), Question.id.desc()).offset(offset).limit(limit)
    )
    items = rows.scalars().all()
    log_event("question_bank.list", status="success", result_count=len(items), filter_status=status)
    return QuestionBankListOut(items=[_question_out(item) for item in items], total=total or 0)


@router.post("", response_model=QuestionBankQuestionOut)
async def create_managed_question(
    payload: QuestionBankCreateRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_content_operator_or_admin),
) -> QuestionBankQuestionOut:
    now = _now()
    company = await _resolve_company(db, payload.company_id, payload.company_name)
    position = await _resolve_position(db, payload.position_id, payload.position_name)
    question = Question(
        title=payload.title,
        body=payload.prompt,
        answer_key=payload.answer_reference,
        difficulty=payload.difficulty,
        qtype=payload.qtype,
        source_type="managed",
        source_note=payload.source_note,
        company_id=company.id if company else None,
        position_id=position.id if position else None,
        status=payload.status,
        created_by_user_id=operator.id,
        updated_by_user_id=operator.id,
        updated_at=now,
        published_at=now if payload.status == QUESTION_STATUS_PUBLISHED else None,
    )
    db.add(question)
    await db.flush()
    await _replace_tags(db, question, payload.tags)
    await db.commit()
    question = await _load_question(db, question.id)
    await _record_question_audit(db, action="question_created", actor=operator, question=question, request=request)
    log_event("question_bank.create", status="success", question_id=question.id)
    return _question_out(question)


@router.patch("/{question_id}", response_model=QuestionBankQuestionOut)
async def update_managed_question(
    question_id: int,
    payload: QuestionBankUpdateRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_content_operator_or_admin),
) -> QuestionBankQuestionOut:
    question = await _load_question(db, question_id)
    changed_fields = sorted(payload.model_fields_set)

    if "title" in payload.model_fields_set:
        question.title = str(payload.title)
    if "prompt" in payload.model_fields_set:
        question.body = payload.prompt
    if "answer_reference" in payload.model_fields_set:
        question.answer_key = str(payload.answer_reference)
    if "difficulty" in payload.model_fields_set and payload.difficulty is not None:
        question.difficulty = payload.difficulty
    if "qtype" in payload.model_fields_set and payload.qtype is not None:
        question.qtype = payload.qtype
    if "source_note" in payload.model_fields_set:
        question.source_note = payload.source_note
    if "company_id" in payload.model_fields_set or "company_name" in payload.model_fields_set:
        company = await _resolve_company(db, payload.company_id, payload.company_name)
        question.company_id = company.id if company else None
    if "position_id" in payload.model_fields_set or "position_name" in payload.model_fields_set:
        position = await _resolve_position(db, payload.position_id, payload.position_name)
        question.position_id = position.id if position else None
    if payload.tags is not None:
        await _replace_tags(db, question, payload.tags)

    question.updated_by_user_id = operator.id
    question.updated_at = _now()
    await db.commit()
    question = await _load_question(db, question.id)
    await _record_question_audit(
        db,
        action="question_updated",
        actor=operator,
        question=question,
        request=request,
        changed_fields=changed_fields,
    )
    log_event("question_bank.update", status="success", question_id=question.id, changed_fields=changed_fields)
    return _question_out(question)


@router.post("/{question_id}/publish", response_model=QuestionBankQuestionOut)
async def publish_managed_question(
    question_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_content_operator_or_admin),
) -> QuestionBankQuestionOut:
    question = await _load_question(db, question_id)
    now = _now()
    question.status = QUESTION_STATUS_PUBLISHED
    question.updated_by_user_id = operator.id
    question.updated_at = now
    question.published_at = question.published_at or now
    question.archived_at = None
    await db.commit()
    question = await _load_question(db, question.id)
    await _record_question_audit(db, action="question_published", actor=operator, question=question, request=request)
    log_event("question_bank.publish", status="success", question_id=question.id)
    return _question_out(question)


@router.post("/{question_id}/archive", response_model=QuestionBankQuestionOut)
async def archive_managed_question(
    question_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_content_operator_or_admin),
) -> QuestionBankQuestionOut:
    question = await _load_question(db, question_id)
    now = _now()
    question.status = "archived"
    question.updated_by_user_id = operator.id
    question.updated_at = now
    question.archived_at = now
    await db.commit()
    question = await _load_question(db, question.id)
    await _record_question_audit(db, action="question_archived", actor=operator, question=question, request=request)
    log_event("question_bank.archive", status="success", question_id=question.id)
    return _question_out(question)
