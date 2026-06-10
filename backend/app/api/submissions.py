from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.ingest.review_queue import precheck_question
from app.models import QuestionSubmission
from app.schemas import SubmissionCreate, SubmissionOut


router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut)
async def create_submission(
    request: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
) -> SubmissionOut:
    decision = precheck_question(request.title, request.answer_key)
    status = "pending_review" if decision.status == "active" else decision.status
    submission = QuestionSubmission(
        submitter_name=request.submitter_name,
        company_name=request.company_name,
        position_name=request.position_name,
        title=request.title,
        body=request.body,
        answer_key=request.answer_key,
        difficulty=request.difficulty,
        qtype=request.qtype,
        source_type="ugc",
        tags=[{"name": tag.strip(), "category": "ugc"} for tag in request.tags if tag.strip()],
        status=status,
        review_note=decision.reason,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return SubmissionOut.model_validate(submission)
