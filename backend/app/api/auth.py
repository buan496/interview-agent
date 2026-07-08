from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Protocol

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit_event
from app.db import get_db
from app.models import User
from app.observability import log_event, mask_phone, set_user_context
from app.rate_limit import RateLimitExceeded, check_auth_rate_limits, rate_limit_http_exception
from app.rbac import ROLE_USER, can_manage_question_bank, admin_access_decision, get_user_role
from app.settings import ConfigValidationError, DEFAULT_DEV_CODE, DEFAULT_JWT_SECRET, Settings, get_settings


router = APIRouter(prefix="/auth", tags=["auth"])


class RequestCodeRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)


class LoginRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class SmsCodeVerifier(Protocol):
    def verify(self, phone: str, code: str) -> bool:
        ...


class DevSmsCodeVerifier:
    def __init__(self, expected_code: str) -> None:
        self.expected_code = expected_code

    def verify(self, phone: str, code: str) -> bool:
        return bool(phone) and hmac.compare_digest(code, self.expected_code)


class ProductionSmsCodeVerifier:
    def verify(self, phone: str, code: str) -> bool:
        # Placeholder for a real provider. Until integrated, production must not
        # silently accept any code.
        return False


def _ensure_auth_config(settings: Settings) -> None:
    validate = getattr(settings, "validate_production_config", None)
    if callable(validate):
        try:
            validate()
        except ConfigValidationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return
    if settings.is_production and settings.jwt_secret == DEFAULT_JWT_SECRET:
        raise HTTPException(status_code=500, detail="Production JWT secret is not configured")
    if settings.is_production and settings.auth_dev_code == DEFAULT_DEV_CODE:
        raise HTTPException(status_code=500, detail="Production auth cannot use the default development code")
    if settings.is_production and settings.auth_dev_code_enabled:
        raise HTTPException(status_code=500, detail="Production auth cannot enable development verification code")


def _sms_verifier(settings: Settings) -> SmsCodeVerifier:
    _ensure_auth_config(settings)
    if settings.auth_dev_code_enabled and not settings.is_production:
        return DevSmsCodeVerifier(settings.auth_dev_code)
    return ProductionSmsCodeVerifier()


def verify_sms_code(phone: str, code: str, settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return _sms_verifier(active_settings).verify(phone, code)


def _encode(payload: dict) -> str:
    settings = get_settings()
    _ensure_auth_config(settings)
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{raw}.{encoded_signature}"


def _decode(token: str) -> dict:
    settings = get_settings()
    _ensure_auth_config(settings)
    try:
        raw, encoded_signature = token.split(".", 1)
        expected = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, actual):
            raise ValueError("signature mismatch")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1]


async def _get_or_create_user(db: AsyncSession, phone: str) -> User:
    user = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
    if user:
        return user
    user = User(phone=phone, nickname=f"用户{phone[-4:]}", role=ROLE_USER)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> User:
    payload = _decode(_bearer_token(authorization))
    phone = str(payload.get("sub") or "")
    if not phone:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user = await _get_or_create_user(db, phone)
    set_user_context(user.id)
    if request is not None:
        request.state.user_id = user.id
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    decision = admin_access_decision(current_user, get_settings())
    audit_metadata = {
        "method": request.method if request else None,
        "path": request.url.path if request else None,
        "required_role": "admin",
        "user_role": decision.user_role,
        "access_source": decision.access_source,
    }
    if not decision.allowed:
        if isinstance(db, AsyncSession):
            await record_audit_event(
                db,
                action="admin_denied",
                status="denied",
                actor=current_user,
                actor_role=decision.user_role,
                resource_type="admin",
                request=request,
                reason=decision.reason,
                metadata=audit_metadata,
            )
        raise HTTPException(status_code=403, detail="Admin privileges required")
    if isinstance(db, AsyncSession):
        await record_audit_event(
            db,
            action="admin_access",
            status="success",
            actor=current_user,
            actor_role=decision.user_role,
            resource_type="admin",
            request=request,
            metadata=audit_metadata,
        )
    return current_user


async def require_content_operator_or_admin(
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()
    user_role = get_user_role(current_user)
    allowed = can_manage_question_bank(current_user, settings)
    access_source = "role" if user_role in {"admin", "content_operator"} else "admin_phone_fallback"
    audit_metadata = {
        "method": request.method if request else None,
        "path": request.url.path if request else None,
        "required_role": "admin_or_content_operator",
        "user_role": user_role,
        "access_source": access_source if allowed else None,
    }
    if not allowed:
        if isinstance(db, AsyncSession):
            await record_audit_event(
                db,
                action="question_bank_denied",
                status="denied",
                actor=current_user,
                actor_role=user_role,
                resource_type="question",
                request=request,
                reason="question_bank_rbac_denied",
                metadata=audit_metadata,
            )
        raise HTTPException(status_code=403, detail="Question bank operator privileges required")
    return current_user


@router.post("/request-code")
async def request_code(request: RequestCodeRequest, http_request: Request = None) -> dict[str, str | int]:
    settings = get_settings()
    _ensure_auth_config(settings)
    try:
        check_auth_rate_limits(http_request, request.phone, settings)
    except RateLimitExceeded as exc:
        raise rate_limit_http_exception(exc) from exc
    if settings.is_production and not settings.sms_provider_key:
        log_event("auth.request_code", status="failed", phone=mask_phone(request.phone), reason="sms_provider_missing")
        raise HTTPException(status_code=503, detail="SMS provider is not configured")
    response: dict[str, str | int] = {"status": "sent", "expires_in": 300}
    if settings.auth_dev_code_enabled and not settings.is_production:
        response["development_code"] = settings.auth_dev_code
    log_event("auth.request_code", status="success", phone=mask_phone(request.phone), dev_code_enabled=settings.auth_dev_code_enabled)
    return response


@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
) -> dict[str, str | int]:
    settings = get_settings()
    try:
        check_auth_rate_limits(http_request, request.phone, settings)
    except RateLimitExceeded as exc:
        raise rate_limit_http_exception(exc) from exc
    if not verify_sms_code(request.phone, request.code, settings):
        log_event("auth.login", status="failed", phone=mask_phone(request.phone), reason="invalid_code")
        if isinstance(db, AsyncSession):
            await record_audit_event(
                db,
                action="login_failed",
                status="failed",
                actor_phone=request.phone,
                actor_role="anonymous",
                resource_type="auth",
                request=http_request,
                reason="invalid_code",
                metadata={"auth_method": "sms_code"},
            )
        raise HTTPException(status_code=401, detail="Invalid verification code")
    user = await _get_or_create_user(db, request.phone)
    set_user_context(user.id)
    if http_request is not None:
        http_request.state.user_id = user.id
    expires_in = settings.access_token_expire_minutes * 60
    token = _encode({"sub": request.phone, "uid": user.id, "exp": int(time.time()) + expires_in})
    log_event("auth.login", status="success", phone=mask_phone(request.phone), user_id=user.id)
    if isinstance(db, AsyncSession):
        await record_audit_event(
            db,
            action="login_success",
            status="success",
            actor=user,
            actor_role=get_user_role(user),
            resource_type="auth",
            request=http_request,
            metadata={"auth_method": "sms_code"},
        )
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"phone": str(current_user.phone)}
