from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.async_jobs import JOB_TYPE_MEMORY_REFRESH, create_async_job
from app.db import get_db
from app.memory import (
    ACTIVE,
    MEMORY_STATUSES,
    MEMORY_TYPES,
    active_memory_count,
    archive_user_memory,
    list_user_memories,
    refresh_user_memories,
)
from app.models import User
from app.observability import log_event
from app.schemas import AgentMemoryListOut, AgentMemoryOut, AgentMemoryRefreshOut, AsyncJobCreateOut, AsyncJobOut


router = APIRouter(prefix="/me/memories", tags=["memories"])


@router.get("", response_model=AgentMemoryListOut)
async def memories(
    memory_type: str | None = Query(default=None),
    status: str = Query(default=ACTIVE),
    tag: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryListOut:
    if memory_type is not None and memory_type not in MEMORY_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported memory_type")
    if status not in MEMORY_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported status")
    items, total = await list_user_memories(
        db,
        user_id=current_user.id,
        memory_type=memory_type,
        status=status,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    log_event("memory.list", status="success", result_count=len(items), total=total)
    return AgentMemoryListOut(items=[AgentMemoryOut.model_validate(item) for item in items], total=total)


@router.post("/{memory_id}/archive", response_model=AgentMemoryOut)
async def archive_memory(
    memory_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryOut:
    memory = await archive_user_memory(db, user_id=current_user.id, memory_id=memory_id)
    if not memory:
        log_event("memory.archive", status="not_found", memory_id=memory_id)
        raise HTTPException(status_code=404, detail="Memory not found")
    log_event("memory.archive", status="success", memory_id=memory.id, memory_type=memory.memory_type)
    return AgentMemoryOut.model_validate(memory)


@router.post("/refresh", response_model=AgentMemoryRefreshOut)
async def refresh_memories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentMemoryRefreshOut:
    stats = await refresh_user_memories(db, user_id=current_user.id, trigger="manual")
    total_active = await active_memory_count(db, current_user.id)
    return AgentMemoryRefreshOut(created=stats.created, updated=stats.updated, total_active=total_active)


@router.post("/refresh-async", response_model=AsyncJobCreateOut)
async def refresh_memories_async(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobCreateOut:
    job = await create_async_job(
        db,
        job_type=JOB_TYPE_MEMORY_REFRESH,
        user_id=current_user.id,
        payload={"user_id": current_user.id, "trigger": "manual_async"},
    )
    log_event("memory.refresh_async", status="queued", job_id=job.id, job_type=job.job_type)
    return AsyncJobCreateOut(job_id=job.id, status=job.status, job=AsyncJobOut.model_validate(job))
