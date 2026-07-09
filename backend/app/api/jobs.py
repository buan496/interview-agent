from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.async_jobs import get_user_job, list_user_jobs
from app.db import get_db
from app.models import User
from app.observability import log_event
from app.schemas import AsyncJobListOut, AsyncJobOut


router = APIRouter(prefix="/me/jobs", tags=["jobs"])


@router.get("", response_model=AsyncJobListOut)
async def jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobListOut:
    items, total = await list_user_jobs(
        db,
        user_id=current_user.id,
        status=status,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    log_event("async_job.list", status="success", result_count=len(items), total=total)
    return AsyncJobListOut(items=[AsyncJobOut.model_validate(item) for item in items], total=total)


@router.get("/{job_id}", response_model=AsyncJobOut)
async def job_detail(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobOut:
    job = await get_user_job(db, user_id=current_user.id, job_id=job_id)
    if job is None:
        log_event("async_job.read", status="not_found", job_id=job_id)
        raise HTTPException(status_code=404, detail="Job not found")
    log_event("async_job.read", status="success", job_id=job.id, job_type=job.job_type, job_status=job.status)
    return AsyncJobOut.model_validate(job)
