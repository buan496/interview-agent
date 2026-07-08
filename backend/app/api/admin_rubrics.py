from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_rubric_operator_or_admin
from app.audit import record_audit_event
from app.db import get_db
from app.models import ScoringRubric, ScoringRubricVersion, User
from app.observability import log_event
from app.rubrics import RUBRIC_STATUSES, RUBRIC_STATUS_ARCHIVED, RUBRIC_STATUS_PUBLISHED
from app.schemas import RubricCreateRequest, RubricListOut, RubricOut, RubricVersionCreateRequest, RubricVersionOut


router = APIRouter(prefix="/admin/rubrics", tags=["admin-rubrics"])
version_router = APIRouter(prefix="/admin/rubric-versions", tags=["admin-rubrics"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_rubric(db: AsyncSession, rubric_id: int) -> ScoringRubric:
    rubric = (
        await db.execute(
            select(ScoringRubric)
            .where(ScoringRubric.id == rubric_id)
            .options(selectinload(ScoringRubric.versions))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return rubric


async def _load_version(db: AsyncSession, version_id: int) -> ScoringRubricVersion:
    version = await db.get(ScoringRubricVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Rubric version not found")
    return version


async def _record_rubric_audit(
    db: AsyncSession,
    *,
    action: str,
    actor: User,
    request: Request | None,
    rubric: ScoringRubric | None = None,
    version: ScoringRubricVersion | None = None,
) -> None:
    await record_audit_event(
        db,
        action=action,
        status="success",
        actor=actor,
        actor_role=actor.role,
        resource_type="rubric_version" if version else "rubric",
        resource_id=version.id if version else rubric.id if rubric else None,
        request=request,
        metadata={
            "rubric_id": version.rubric_id if version else rubric.id if rubric else None,
            "rubric_status": rubric.status if rubric else None,
            "version_id": version.id if version else None,
            "version": version.version if version else None,
            "version_status": version.status if version else None,
            "dimension_count": len(version.dimensions_json or []) if version else None,
            "template_length": len(version.prompt_template) if version else None,
            "scoring_scale": version.scoring_scale if version else None,
        },
    )


@router.get("", response_model=RubricListOut)
async def list_rubrics(
    status: str | None = Query(default=None, max_length=15),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricListOut:
    if status and status not in RUBRIC_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported rubric status")
    stmt = select(ScoringRubric)
    if status:
        stmt = stmt.where(ScoringRubric.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await db.execute(
        stmt.options(selectinload(ScoringRubric.versions))
        .order_by(ScoringRubric.updated_at.desc(), ScoringRubric.id.desc())
        .offset(offset)
        .limit(limit)
    )
    items = rows.scalars().all()
    log_event("rubric.list", status="success", result_count=len(items), filter_status=status)
    return RubricListOut(items=[RubricOut.model_validate(item) for item in items], total=total or 0)


@router.post("", response_model=RubricOut)
async def create_rubric(
    payload: RubricCreateRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricOut:
    existing = (await db.execute(select(ScoringRubric).where(ScoringRubric.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Rubric name already exists")
    now = _now()
    rubric = ScoringRubric(
        name=payload.name,
        description=payload.description,
        status=payload.status,
        created_by_user_id=operator.id,
        updated_by_user_id=operator.id,
        created_at=now,
        updated_at=now,
    )
    db.add(rubric)
    await db.commit()
    rubric = await _load_rubric(db, rubric.id)
    await _record_rubric_audit(db, action="rubric_created", actor=operator, request=request, rubric=rubric)
    log_event("rubric.create", status="success", rubric_id=rubric.id)
    return RubricOut.model_validate(rubric)


@router.get("/{rubric_id}", response_model=RubricOut)
async def get_rubric(
    rubric_id: int,
    db: AsyncSession = Depends(get_db),
    _operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricOut:
    rubric = await _load_rubric(db, rubric_id)
    log_event("rubric.read", status="success", rubric_id=rubric.id)
    return RubricOut.model_validate(rubric)


@router.post("/{rubric_id}/versions", response_model=RubricVersionOut)
async def create_rubric_version(
    rubric_id: int,
    payload: RubricVersionCreateRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricVersionOut:
    rubric = await _load_rubric(db, rubric_id)
    existing = (
        await db.execute(
            select(ScoringRubricVersion).where(
                ScoringRubricVersion.rubric_id == rubric_id,
                ScoringRubricVersion.version == payload.version,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Rubric version already exists")
    version = ScoringRubricVersion(
        rubric_id=rubric.id,
        version=payload.version,
        dimensions_json=payload.dimensions_json,
        prompt_template=payload.prompt_template,
        scoring_scale=payload.scoring_scale,
        status="draft",
        created_by_user_id=operator.id,
        created_at=_now(),
    )
    rubric.updated_by_user_id = operator.id
    rubric.updated_at = _now()
    db.add(version)
    await db.commit()
    version = await _load_version(db, version.id)
    await _record_rubric_audit(db, action="rubric_version_created", actor=operator, request=request, rubric=rubric, version=version)
    log_event("rubric_version.create", status="success", rubric_id=rubric.id, rubric_version_id=version.id)
    return RubricVersionOut.model_validate(version)


@version_router.post("/{version_id}/publish", response_model=RubricVersionOut)
async def publish_rubric_version(
    version_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricVersionOut:
    version = await _load_version(db, version_id)
    rubric = await _load_rubric(db, version.rubric_id)
    now = _now()
    version.status = RUBRIC_STATUS_PUBLISHED
    version.published_at = version.published_at or now
    version.archived_at = None
    rubric.status = RUBRIC_STATUS_PUBLISHED
    rubric.updated_by_user_id = operator.id
    rubric.updated_at = now
    await db.commit()
    version = await _load_version(db, version.id)
    await _record_rubric_audit(db, action="rubric_version_published", actor=operator, request=request, rubric=rubric, version=version)
    log_event("rubric_version.publish", status="success", rubric_id=rubric.id, rubric_version_id=version.id)
    return RubricVersionOut.model_validate(version)


@version_router.post("/{version_id}/archive", response_model=RubricVersionOut)
async def archive_rubric_version(
    version_id: int,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    operator: User = Depends(require_rubric_operator_or_admin),
) -> RubricVersionOut:
    version = await _load_version(db, version_id)
    rubric = await _load_rubric(db, version.rubric_id)
    now = _now()
    version.status = RUBRIC_STATUS_ARCHIVED
    version.archived_at = now
    rubric.updated_by_user_id = operator.id
    rubric.updated_at = now
    await db.commit()
    version = await _load_version(db, version.id)
    await _record_rubric_audit(db, action="rubric_version_archived", actor=operator, request=request, rubric=rubric, version=version)
    log_event("rubric_version.archive", status="success", rubric_id=rubric.id, rubric_version_id=version.id)
    return RubricVersionOut.model_validate(version)
