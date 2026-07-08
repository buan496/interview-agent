from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, User
from app.observability import get_request_id, log_exception, mask_phone


SENSITIVE_METADATA_KEYS = {
    "answer",
    "answer_text",
    "authorization",
    "code",
    "completion",
    "completion_text",
    "jwt",
    "password",
    "phone",
    "prompt",
    "prompt_text",
    "secret",
    "token",
    "verification_code",
}


def mask_audit_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(sensitive in normalized_key for sensitive in SENSITIVE_METADATA_KEYS):
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = mask_audit_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [mask_audit_metadata(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [mask_audit_metadata(item) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_audit_context_from_request(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"request_id": get_request_id(), "ip_address": None, "user_agent": None}
    return {
        "request_id": getattr(request.state, "request_id", None) or get_request_id(),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def record_audit_event(
    db: AsyncSession,
    *,
    action: str,
    status: str,
    actor: User | None = None,
    actor_user_id: int | None = None,
    actor_phone: str | None = None,
    actor_role: str = "anonymous",
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    target_user_id: int | None = None,
    request: Request | None = None,
    request_id: str | None = None,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    context = build_audit_context_from_request(request)
    active_actor_user_id = actor_user_id if actor_user_id is not None else getattr(actor, "id", None)
    active_actor_phone = actor_phone if actor_phone is not None else getattr(actor, "phone", None)
    try:
        event = AuditEvent(
            actor_user_id=active_actor_user_id,
            actor_phone_masked=mask_phone(active_actor_phone),
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            target_user_id=target_user_id,
            request_id=request_id or context["request_id"],
            status=status,
            reason=reason,
            ip_address=context["ip_address"],
            user_agent=context["user_agent"],
            metadata_json=mask_audit_metadata(metadata or {}),
        )
        db.add(event)
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
        log_exception(
            "audit.write_failed",
            action=action,
            audit_status=status,
            actor_user_id=active_actor_user_id,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
        )
