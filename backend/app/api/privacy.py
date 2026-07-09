from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit_event
from app.api.auth import get_current_user
from app.data_lifecycle import CONFIRMATION_PHRASE, build_user_data_export, delete_user_training_data, get_user_data_summary
from app.db import get_db
from app.metrics import record_data_deletion, record_data_export
from app.models import User
from app.schemas import DataDeletionConfirmRequest, DataDeletionOut, DataDeletionRequestOut, DataExportOut, DataSummaryOut


router = APIRouter(prefix="/me", tags=["privacy"])


@router.get("/data-summary", response_model=DataSummaryOut)
async def data_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataSummaryOut:
    return DataSummaryOut(**(await get_user_data_summary(db, current_user.id)))


@router.get("/data-export", response_model=DataExportOut)
async def data_export(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataExportOut:
    payload = await build_user_data_export(db, current_user)
    counts = payload.get("summary", {}).get("counts", {})
    await record_audit_event(
        db,
        action="user_data_exported",
        status="success",
        actor=current_user,
        actor_role=current_user.role,
        resource_type="user_data",
        target_user_id=current_user.id,
        request=request,
        metadata={"record_counts": counts},
    )
    record_data_export("success")
    return DataExportOut(**payload)


@router.post("/data-deletion-request", response_model=DataDeletionRequestOut)
async def data_deletion_request(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataDeletionRequestOut:
    summary = await get_user_data_summary(db, current_user.id)
    await record_audit_event(
        db,
        action="user_data_deletion_requested",
        status="success",
        actor=current_user,
        actor_role=current_user.role,
        resource_type="user_data",
        target_user_id=current_user.id,
        request=request,
        metadata={"record_counts": summary["counts"], "scope": "training_data"},
    )
    return DataDeletionRequestOut(
        scope="training_data",
        confirmation_phrase=CONFIRMATION_PHRASE,
        impact=summary["counts"],
        warning="This deletes current-user training data only. The user account and sanitized audit events are retained.",
    )


@router.post("/data-delete-confirm", response_model=DataDeletionOut)
async def data_delete_confirm(
    payload: DataDeletionConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataDeletionOut:
    if payload.confirmation_phrase != CONFIRMATION_PHRASE:
        await record_audit_event(
            db,
            action="user_data_delete_denied",
            status="denied",
            actor=current_user,
            actor_role=current_user.role,
            resource_type="user_data",
            target_user_id=current_user.id,
            request=request,
            reason="invalid_confirmation_phrase",
            metadata={"scope": "training_data"},
        )
        record_data_deletion("denied", "training_data")
        raise HTTPException(status_code=400, detail="Invalid confirmation phrase")

    result = await delete_user_training_data(db, current_user.id)
    await record_audit_event(
        db,
        action="user_data_deleted",
        status="success",
        actor=current_user,
        actor_role=current_user.role,
        resource_type="user_data",
        target_user_id=current_user.id,
        request=request,
        metadata=result,
    )
    record_data_deletion("success", "training_data")
    return DataDeletionOut(**result)
