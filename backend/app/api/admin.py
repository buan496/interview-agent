from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService
from app.db import get_db
from app.ingest.generator import generate_from_jd
from app.ingest.review_queue import precheck_question
from app.models import Company, Position, Question, QuestionSubmission, QuestionTag, Tag
from app.schemas import (
    GenerateFromJdRequest,
    GeneratedSubmissionOut,
    ReviewSubmissionRequest,
    SubmissionOut,
)


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
async def admin_health() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/submissions", response_model=list[SubmissionOut])
async def list_submissions(
    status: str | None = Query(default="pending_review"),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionOut]:
    stmt = select(QuestionSubmission)
    if status:
        stmt = stmt.where(QuestionSubmission.status == status)
    rows = (await db.execute(stmt.order_by(QuestionSubmission.created_at.desc()).limit(200))).scalars().all()
    return [SubmissionOut.model_validate(item) for item in rows]


async def _company(db: AsyncSession, name: str) -> Company:
    item = (await db.execute(select(Company).where(Company.name == name))).scalar_one_or_none()
    if item:
        return item
    item = Company(name=name, region="CN", tier=2)
    db.add(item)
    await db.flush()
    return item


async def _position(db: AsyncSession, name: str) -> Position:
    item = (await db.execute(select(Position).where(Position.name == name))).scalar_one_or_none()
    if item:
        return item
    item = Position(name=name)
    db.add(item)
    await db.flush()
    return item


async def _tag(db: AsyncSession, name: str, category: str | None) -> Tag:
    item = (await db.execute(select(Tag).where(Tag.name == name))).scalar_one_or_none()
    if item:
        return item
    item = Tag(name=name, category=category)
    db.add(item)
    await db.flush()
    return item


@router.patch("/submissions/{submission_id}", response_model=SubmissionOut)
async def review_submission(
    submission_id: int,
    request: ReviewSubmissionRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmissionOut:
    submission = await db.get(QuestionSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status not in {"pending_review", "rejected"}:
        raise HTTPException(status_code=409, detail="Submission has already been approved")

    if request.action == "reject":
        submission.status = "rejected"
        submission.review_note = request.note or "人工审核未通过"
        submission.reviewed_at = datetime.now()
    else:
        duplicate = (
            await db.execute(select(Question).where(Question.title == submission.title))
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="Question with the same title already exists")
        embedding_service = EmbeddingService()
        submission_embedding = await embedding_service.embed_question(submission.title, submission.body)
        existing_questions = (await db.execute(select(Question.id, Question.title, Question.body))).all()
        candidate_embeddings = [
            (question_id, await embedding_service.embed_question(title, body))
            for question_id, title, body in existing_questions
        ]
        duplicate_check = await embedding_service.check_duplicate(submission_embedding, candidate_embeddings)
        if duplicate_check.is_duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Potential duplicate of question {duplicate_check.matched_question_id} "
                    f"(similarity={duplicate_check.similarity:.3f})"
                ),
            )
        company = await _company(db, submission.company_name)
        position = await _position(db, submission.position_name)
        question = Question(
            title=submission.title,
            body=submission.body,
            answer_key=submission.answer_key,
            difficulty=submission.difficulty,
            qtype=submission.qtype,
            source_type=submission.source_type,
            source_note=f"reviewed submission #{submission.id}",
            company_id=company.id,
            position_id=position.id,
            status="active",
        )
        db.add(question)
        await db.flush()
        for tag_data in submission.tags:
            tag = await _tag(db, str(tag_data.get("name") or "其他"), tag_data.get("category"))
            db.add(QuestionTag(question_id=question.id, tag_id=tag.id))
        submission.status = "approved"
        submission.review_note = request.note or "人工审核通过"
        submission.created_question_id = question.id
        submission.reviewed_at = datetime.now()

    await db.commit()
    await db.refresh(submission)
    return SubmissionOut.model_validate(submission)


@router.post("/generate", response_model=GeneratedSubmissionOut)
async def generate_submissions(
    request: GenerateFromJdRequest,
    db: AsyncSession = Depends(get_db),
) -> GeneratedSubmissionOut:
    generated = await generate_from_jd(request.jd_text, request.company, request.position, request.count)
    submissions = []
    for item in generated:
        decision = precheck_question(item.title, item.answer_key)
        submission = QuestionSubmission(
            company_name=request.company,
            position_name=request.position,
            title=item.title,
            body=item.body,
            answer_key=item.answer_key,
            difficulty=item.difficulty,
            qtype=item.qtype,
            source_type="generated",
            tags=[],
            status="pending_review",
            review_note=decision.reason,
        )
        db.add(submission)
        submissions.append(submission)
    await db.commit()
    for item in submissions:
        await db.refresh(item)
    return GeneratedSubmissionOut(items=[SubmissionOut.model_validate(item) for item in submissions])
